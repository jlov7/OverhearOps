import json
from pathlib import Path

import httpx
import pytest

from apps.service.runtime_config import PROMPT_REGISTRY_PATH, RUNTIME_SETTINGS_PATH
from packages.agentkit.provider import (
    LLMProvider,
    OfflineProvider,
    OpenAIResponsesProvider,
    RecordingProvider,
    resolve_provider,
)


def test_resolve_provider_offline_mode() -> None:
    provider = resolve_provider(
        mode="offline",
        provider_name="offline",
        base_dir="data/demo/llm",
    )
    assert isinstance(provider, OfflineProvider)


def test_resolve_provider_live_openai_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        resolve_provider(mode="live", provider_name="openai")


def test_openai_provider_parses_output_text(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"output_text": json.dumps({"winner_plan_id": "plan-timeout"})}

    def fake_post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
        assert url.endswith("/responses")
        assert headers["Authorization"].startswith("Bearer ")
        assert json["text"] == {"format": {"type": "json_object"}}
        assert isinstance(json["instructions"], str)
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    provider = OpenAIResponsesProvider(api_key="test-key", model="gpt-test")
    payload = provider.generate_json(task="judge", thread_id="ci_flake", payload={"plans": []})
    assert payload["winner_plan_id"] == "plan-timeout"


def test_openai_provider_retries_transient_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "retryable",
                    request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
                    response=httpx.Response(self.status_code),
                )

        def json(self) -> dict[str, object]:
            return self._payload

    attempts = {"count": 0}

    def fake_post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return FakeResponse(status_code=429)
        return FakeResponse(
            status_code=200,
            payload={"output_text": "{\"winner_plan_id\":\"plan-timeout\"}"},
        )

    monkeypatch.setenv("OVERHEAROPS_OPENAI_MAX_RETRIES", "2")
    monkeypatch.setenv("OVERHEAROPS_OPENAI_RETRY_BACKOFF_S", "0")
    monkeypatch.setattr(httpx.Client, "post", fake_post)

    provider = OpenAIResponsesProvider(api_key="test-key", model="gpt-test")
    payload = provider.generate_json(task="judge", thread_id="ci_flake", payload={"plans": []})
    assert payload["winner_plan_id"] == "plan-timeout"
    assert attempts["count"] == 3


def test_recording_provider_writes_payload(tmp_path: Path) -> None:
    class StaticProvider(LLMProvider):
        def generate_json(
            self,
            task: str,
            thread_id: str,
            payload: dict[str, object] | None = None,
        ) -> object:
            return {"task": task, "thread_id": thread_id}

    provider = RecordingProvider(delegate=StaticProvider(), base_dir=str(tmp_path))
    output = provider.generate_json(task="custom_task", thread_id="ci_flake")

    assert output == {"task": "custom_task", "thread_id": "ci_flake"}
    stored = tmp_path / "ci_flake" / "custom_task.json"
    assert stored.exists()
    assert json.loads(stored.read_text(encoding="utf-8")) == output


def test_resolve_provider_record_mode_wraps_delegate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OVERHEAROPS_LLM_BASE_DIR", str(tmp_path))

    def fake_generate(
        self: OpenAIResponsesProvider,
        task: str,
        thread_id: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        return {"winner_plan_id": "plan-quarantine"}

    monkeypatch.setattr(OpenAIResponsesProvider, "generate_json", fake_generate)

    provider = resolve_provider(mode="record", provider_name="openai")
    assert isinstance(provider, RecordingProvider)

    output = provider.generate_json(task="judge", thread_id="ci_flake")
    assert output["winner_plan_id"] == "plan-quarantine"
    stored = tmp_path / "ci_flake" / "judge.json"
    assert stored.exists()


def test_openai_provider_uses_fallback_model(monkeypatch: pytest.MonkeyPatch) -> None:
    original_settings = json.loads(RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
    tuned_settings = json.loads(json.dumps(original_settings))
    tuned_settings["model_routing"]["judge"]["model"] = "gpt-primary"
    tuned_settings["model_routing"]["judge"]["fallback_model"] = "gpt-fallback"
    RUNTIME_SETTINGS_PATH.write_text(
        json.dumps(tuned_settings, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "failure",
                    request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
                    response=httpx.Response(self.status_code),
                )

        def json(self) -> dict[str, object]:
            return self._payload

    calls: list[str] = []

    def fake_post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
        model = str(json["model"])
        calls.append(model)
        if model == "gpt-primary":
            return FakeResponse(status_code=500)
        return FakeResponse(
            status_code=200,
            payload={"output_text": "{\"winner_plan_id\":\"plan-timeout\",\"votes\":[]}"},
        )

    monkeypatch.setenv("OVERHEAROPS_OPENAI_MAX_RETRIES", "0")
    monkeypatch.setattr(httpx.Client, "post", fake_post)

    provider = OpenAIResponsesProvider(
        api_key="test-key",
        model="gpt-primary",
        fallback_model="gpt-fallback",
    )
    try:
        payload = provider.generate_json(task="judge", thread_id="ci_flake")
        assert payload["winner_plan_id"] == "plan-timeout"
        assert calls == ["gpt-primary", "gpt-fallback"]
    finally:
        RUNTIME_SETTINGS_PATH.write_text(
            json.dumps(original_settings, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def test_openai_provider_circuit_breaker_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    original_settings = json.loads(RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
    tuned_settings = json.loads(json.dumps(original_settings))
    tuned_settings["model_routing"]["judge"]["model"] = "gpt-primary"
    tuned_settings["model_routing"]["judge"]["fallback_model"] = ""
    RUNTIME_SETTINGS_PATH.write_text(
        json.dumps(tuned_settings, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    class FakeResponse:
        status_code = 500

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError(
                "failure",
                request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
                response=httpx.Response(self.status_code),
            )

        def json(self) -> dict[str, object]:
            return {}

    attempts = {"count": 0}

    def fake_post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
        attempts["count"] += 1
        return FakeResponse()

    monkeypatch.setenv("OVERHEAROPS_OPENAI_MAX_RETRIES", "0")
    monkeypatch.setenv("OVERHEAROPS_OPENAI_CIRCUIT_FAILURES", "1")
    monkeypatch.setenv("OVERHEAROPS_OPENAI_CIRCUIT_COOLDOWN_S", "60")
    monkeypatch.setattr(httpx.Client, "post", fake_post)

    try:
        provider = OpenAIResponsesProvider(api_key="test-key", model="gpt-primary")
        with pytest.raises(httpx.HTTPStatusError):
            provider.generate_json(task="judge", thread_id="ci_flake")
        with pytest.raises(RuntimeError, match="circuit breaker is open"):
            provider.generate_json(task="judge", thread_id="ci_flake")
        assert attempts["count"] == 1
    finally:
        RUNTIME_SETTINGS_PATH.write_text(
            json.dumps(original_settings, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def test_openai_provider_respects_task_model_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    original = json.loads(RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
    updated = json.loads(json.dumps(original))
    updated["model_routing"]["judge"]["model"] = "routed-judge-model"
    updated["model_routing"]["judge"]["fallback_model"] = "routed-judge-fallback"
    RUNTIME_SETTINGS_PATH.write_text(
        json.dumps(updated, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"output_text": "{\"winner_plan_id\":\"plan-timeout\",\"votes\":[]}"}

    models: list[str] = []

    def fake_post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
        models.append(str(json["model"]))
        return FakeResponse()

    try:
        monkeypatch.setattr(httpx.Client, "post", fake_post)
        provider = OpenAIResponsesProvider(api_key="test-key", model="default-model")
        provider.generate_json(task="judge", thread_id="ci_flake")
        assert models == ["routed-judge-model"]
    finally:
        RUNTIME_SETTINGS_PATH.write_text(
            json.dumps(original, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def test_openai_provider_uses_prompt_registry_instruction(monkeypatch: pytest.MonkeyPatch) -> None:
    original = json.loads(PROMPT_REGISTRY_PATH.read_text(encoding="utf-8"))
    updated = json.loads(json.dumps(original))
    updated["tasks"]["judge"]["selected_version"] = "v2"
    PROMPT_REGISTRY_PATH.write_text(json.dumps(updated, indent=2, sort_keys=True), encoding="utf-8")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"output_text": "{\"winner_plan_id\":\"plan-timeout\",\"votes\":[]}"}

    instructions: list[str] = []

    def fake_post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
        instructions.append(str(json["instructions"]))
        return FakeResponse()

    try:
        monkeypatch.setattr(httpx.Client, "post", fake_post)
        provider = OpenAIResponsesProvider(api_key="test-key", model="default-model")
        provider.generate_json(task="judge", thread_id="ci_flake")
        assert instructions
        assert "tradeoffs" in instructions[0].lower()
    finally:
        PROMPT_REGISTRY_PATH.write_text(
            json.dumps(original, indent=2, sort_keys=True),
            encoding="utf-8",
        )
