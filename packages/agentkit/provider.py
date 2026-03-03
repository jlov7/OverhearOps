from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field, TypeAdapter

from apps.service.runtime_config import get_model_for_task, get_prompt_instruction

TASK_INSTRUCTIONS: dict[str, str] = {
    "plan": (
        "Return JSON only. Produce a list of remediation plan objects with keys: "
        "id, title, hypothesis, steps (array of strings), blast_radius, confidence (0..1)."
    ),
    "judge": (
        "Return JSON only. Produce an object with keys: winner_plan_id, rationale, votes "
        "(array of objects with persona and plan_id)."
    ),
}


class PlanRecord(BaseModel):
    id: str
    title: str
    hypothesis: str
    steps: list[str]
    blast_radius: str
    confidence: float


class JudgeVote(BaseModel):
    persona: str = "agent"
    plan_id: str


class JudgeRecord(BaseModel):
    winner_plan_id: str
    rationale: str = ""
    votes: list[JudgeVote] = Field(default_factory=list)


def _validate_task_output(task: str, output: Any) -> Any:
    if task == "plan":
        records = TypeAdapter(list[PlanRecord]).validate_python(output)
        return [record.model_dump() for record in records]
    if task == "judge":
        return JudgeRecord.model_validate(output).model_dump()
    return output


@dataclass
class ProviderConfig:
    mode: str
    provider: str
    base_dir: str | None = None


class LLMProvider:
    def generate_json(
        self,
        task: str,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        raise NotImplementedError


class OfflineProvider(LLMProvider):
    def __init__(self, base_dir: str = "data/demo/llm") -> None:
        self.base_dir = Path(base_dir)

    def generate_json(
        self,
        task: str,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        path = self.base_dir / thread_id / f"{task}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        return _validate_task_output(task, raw)


class OpenAIResponsesProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5-mini",
        fallback_model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_s: float = 45.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _request_body(
        self,
        task: str,
        thread_id: str,
        model: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        default_instruction = TASK_INSTRUCTIONS.get(
            task,
            "Return valid JSON only that matches the task input.",
        )
        instruction = get_prompt_instruction(task=task, fallback=default_instruction)
        user_payload = {
            "task": task,
            "thread_id": thread_id,
            "payload": payload or {},
        }
        return {
            "model": model,
            "instructions": instruction,
            "input": json.dumps(user_payload, sort_keys=True, default=str),
            "text": {"format": {"type": "json_object"}},
        }

    @staticmethod
    def _extract_output_text(response_payload: dict[str, Any]) -> str:
        output_text = response_payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output = response_payload.get("output", [])
        if not isinstance(output, list):
            return ""
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "\n".join(chunks).strip()

    @staticmethod
    def _decode_json_output(text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            compact = " ".join(text.split())
            snippet = compact[:240]
            raise RuntimeError(f"OpenAI output was not valid JSON: {snippet}") from exc

    def generate_json(
        self,
        task: str,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        breaker_threshold_raw = os.getenv(
            "OVERHEAROPS_OPENAI_CIRCUIT_FAILURES",
            os.getenv("OVERHEAROPS_EXTERNAL_CIRCUIT_FAILURES", "3"),
        )
        breaker_cooldown_raw = os.getenv(
            "OVERHEAROPS_OPENAI_CIRCUIT_COOLDOWN_S",
            os.getenv("OVERHEAROPS_EXTERNAL_CIRCUIT_COOLDOWN_S", "30"),
        )
        try:
            breaker_threshold = max(1, int(breaker_threshold_raw))
        except ValueError:
            breaker_threshold = 3
        try:
            breaker_cooldown = max(1.0, float(breaker_cooldown_raw))
        except ValueError:
            breaker_cooldown = 30.0
        now = time.time()
        if now < self._circuit_open_until:
            wait_s = int(self._circuit_open_until - now)
            raise RuntimeError(f"OpenAI circuit breaker is open; retry in ~{wait_s}s.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        max_retries_raw = os.getenv(
            "OVERHEAROPS_OPENAI_MAX_RETRIES",
            os.getenv("OVERHEAROPS_EXTERNAL_MAX_RETRIES", "2"),
        )
        retry_backoff_raw = os.getenv(
            "OVERHEAROPS_OPENAI_RETRY_BACKOFF_S",
            os.getenv("OVERHEAROPS_EXTERNAL_RETRY_BACKOFF_S", "0.5"),
        )
        try:
            max_retries = max(0, int(max_retries_raw))
        except ValueError:
            max_retries = 2
        try:
            retry_backoff_s = max(0.0, float(retry_backoff_raw))
        except ValueError:
            retry_backoff_s = 0.5

        routed_model, routed_fallback_model = get_model_for_task(
            task=task,
            default_model=self.model,
            default_fallback=self.fallback_model,
        )
        models = [routed_model]
        if routed_fallback_model and routed_fallback_model != routed_model:
            models.append(routed_fallback_model)

        last_exc: Exception | None = None
        for model_name in models:
            request_body = self._request_body(
                task=task,
                thread_id=thread_id,
                model=model_name,
                payload=payload,
            )
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    response: httpx.Response | None = None
                    for attempt in range(max_retries + 1):
                        response = client.post(
                            f"{self.base_url}/responses",
                            headers=headers,
                            json=request_body,
                        )
                        retryable = response.status_code in {408, 409, 429, 500, 502, 503, 504}
                        if not retryable or attempt == max_retries:
                            break
                        if retry_backoff_s > 0:
                            time.sleep(retry_backoff_s * (2**attempt))
                    if response is None:
                        raise RuntimeError("OpenAI request did not return a response.")
                    response.raise_for_status()
                    response_payload = response.json()
                if not isinstance(response_payload, dict):
                    raise RuntimeError("Unexpected OpenAI Responses payload format.")

                text = self._extract_output_text(response_payload)
                if not text:
                    raise RuntimeError("OpenAI response contained no output text.")
                self._consecutive_failures = 0
                self._circuit_open_until = 0.0
                return _validate_task_output(task, self._decode_json_output(text))
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                continue

        self._consecutive_failures += 1
        if self._consecutive_failures >= breaker_threshold:
            self._circuit_open_until = time.time() + breaker_cooldown
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("OpenAI provider failed without exception context.")


class RecordingProvider(LLMProvider):
    def __init__(self, delegate: LLMProvider, base_dir: str = "data/demo/llm") -> None:
        self.delegate = delegate
        self.base_dir = Path(base_dir)

    def _target_path(self, task: str, thread_id: str) -> Path:
        return self.base_dir / thread_id / f"{task}.json"

    def generate_json(
        self,
        task: str,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        output = self.delegate.generate_json(task=task, thread_id=thread_id, payload=payload)
        normalized = _validate_task_output(task, output)
        target = self._target_path(task=task, thread_id=thread_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        return normalized


def resolve_provider(
    mode: str | None = None,
    provider_name: str | None = None,
    base_dir: str | None = None,
) -> LLMProvider | None:
    mode_raw = mode if mode is not None else os.getenv("OVERHEAROPS_LLM_MODE")
    selected_mode = (mode_raw or "offline").lower()
    provider_raw = (
        provider_name
        if provider_name is not None
        else os.getenv("OVERHEAROPS_LLM_PROVIDER")
    )
    selected_provider = (provider_raw or "offline").lower()

    if selected_mode in {"offline", "replay"}:
        fixture_dir_env = os.getenv("OVERHEAROPS_LLM_BASE_DIR")
        fixture_dir = base_dir or fixture_dir_env or "data/demo/llm"
        return OfflineProvider(fixture_dir)

    if selected_mode in {"live", "record"}:
        if selected_provider != "openai":
            raise RuntimeError(
                f"Unsupported provider '{selected_provider}' for mode '{selected_mode}'."
            )
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY must be set for live/record OpenAI modes.")
        model = os.getenv("OVERHEAROPS_OPENAI_MODEL", "gpt-5-mini")
        fallback_model = os.getenv("OVERHEAROPS_OPENAI_FALLBACK_MODEL")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        live_provider = OpenAIResponsesProvider(
            api_key=api_key,
            model=model,
            fallback_model=fallback_model,
            base_url=base_url,
        )
        if selected_mode == "record":
            fixture_dir_env = os.getenv("OVERHEAROPS_LLM_BASE_DIR")
            fixture_dir = base_dir or fixture_dir_env or "data/demo/llm"
            return RecordingProvider(delegate=live_provider, base_dir=fixture_dir)
        return live_provider

    return None
