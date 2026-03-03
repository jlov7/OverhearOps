"""Microsoft Teams Graph adapter.

Uses app-only OAuth client credentials to fetch chat/channel messages from
Microsoft Graph and normalize them to the demo thread shape.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Generator, Iterable
from datetime import UTC, datetime
from typing import Any

import httpx

RETRYABLE_STATUS_CODES: set[int] = {408, 409, 429, 500, 502, 503, 504}


class TeamsGraphAdapter:
    def __init__(self) -> None:
        self.credential_scope = self._credential_scope()
        self.tenant_id, self.client_id, self.client_secret, self.credential_source = (
            self._resolve_credentials()
        )
        self.graph_base_url = os.getenv("MS_GRAPH_BASE_URL", "https://graph.microsoft.com/v1.0")
        self.scope = os.getenv("MS_GRAPH_SCOPE", "https://graph.microsoft.com/.default")
        self.poll_interval_s = self._env_float("OVERHEAROPS_GRAPH_POLL_INTERVAL_S", 1.0)
        self.stream_polls = self._env_int("OVERHEAROPS_GRAPH_STREAM_POLLS", 1)
        self.timeout_s = self._env_float("OVERHEAROPS_GRAPH_TIMEOUT_S", 15.0)
        self.max_retries = max(0, self._env_int("OVERHEAROPS_EXTERNAL_MAX_RETRIES", 2))
        self.retry_backoff_s = max(
            0.0,
            self._env_float("OVERHEAROPS_EXTERNAL_RETRY_BACKOFF_S", 0.5),
        )
        self.circuit_failures = max(1, self._env_int("OVERHEAROPS_EXTERNAL_CIRCUIT_FAILURES", 3))
        self.circuit_cooldown_s = max(
            1.0,
            self._env_float("OVERHEAROPS_EXTERNAL_CIRCUIT_COOLDOWN_S", 30.0),
        )
        self._token: str | None = None
        self._token_expiry_epoch = 0.0
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._validate()

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    @staticmethod
    def _credential_scope() -> str:
        scope = os.getenv("OVERHEAROPS_CREDENTIAL_SCOPE", "dry_run").strip().lower()
        return scope if scope in {"dry_run", "prod"} else "dry_run"

    def _resolve_credentials(self) -> tuple[str | None, str | None, str | None, str]:
        if self.credential_scope == "prod":
            return (
                os.getenv("MS_PROD_TENANT_ID"),
                os.getenv("MS_PROD_CLIENT_ID"),
                os.getenv("MS_PROD_CLIENT_SECRET"),
                "MS_PROD_*",
            )
        return (
            os.getenv("MS_DRYRUN_TENANT_ID") or os.getenv("MS_TENANT_ID"),
            os.getenv("MS_DRYRUN_CLIENT_ID") or os.getenv("MS_CLIENT_ID"),
            os.getenv("MS_DRYRUN_CLIENT_SECRET") or os.getenv("MS_CLIENT_SECRET"),
            "MS_DRYRUN_* (fallback: MS_*)",
        )

    def _validate(self) -> None:
        if not (self.tenant_id and self.client_id and self.client_secret):
            raise RuntimeError(
                "TeamsGraphAdapter not configured for credential scope "
                f"'{self.credential_scope}'. Set {self.credential_source} credentials "
                "and ensure admin consent for Chat.Read.All / ChannelMessage.Read.All."
            )

    def _token_endpoint(self) -> str:
        tenant = str(self.tenant_id)
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._get_access_token()}"}

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in RETRYABLE_STATUS_CODES
        return False

    def _assert_circuit_closed(self) -> None:
        now = time.time()
        if now < self._circuit_open_until:
            retry_in = max(1, int(self._circuit_open_until - now))
            raise RuntimeError(f"Graph circuit breaker open; retry in ~{retry_in}s.")

    def _execute_with_resilience(
        self,
        operation: str,
        request_fn: Callable[[], httpx.Response],
    ) -> httpx.Response:
        self._assert_circuit_closed()
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = request_fn()
                response.raise_for_status()
                self._consecutive_failures = 0
                self._circuit_open_until = 0.0
                return response
            except Exception as exc:  # noqa: BLE001
                if not self._is_retryable(exc):
                    raise
                last_exc = exc
                if attempt == self.max_retries:
                    break
                if self.retry_backoff_s > 0:
                    time.sleep(self.retry_backoff_s * (2**attempt))
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.circuit_failures:
            self._circuit_open_until = time.time() + self.circuit_cooldown_s
        if last_exc is not None:
            raise RuntimeError(f"Graph operation '{operation}' failed after retries.") from last_exc
        raise RuntimeError(f"Graph operation '{operation}' failed without exception context.")

    def _get_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry_epoch - 30:
            return self._token

        payload = {
            "grant_type": "client_credentials",
            "client_id": str(self.client_id),
            "client_secret": str(self.client_secret),
            "scope": self.scope,
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            response = self._execute_with_resilience(
                operation="token_request",
                request_fn=lambda: client.post(self._token_endpoint(), data=payload),
            )
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("Invalid token response payload from Microsoft identity platform.")
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Token response missing access_token.")
        expires_in_raw = body.get("expires_in", 3600)
        expires_in = int(expires_in_raw) if isinstance(expires_in_raw, int | str) else 3600
        self._token = token
        self._token_expiry_epoch = now + max(60, expires_in)
        return token

    @staticmethod
    def _normalize_message(item: dict[str, Any]) -> dict[str, Any]:
        sender = (
            item.get("from", {})
            .get("user", {})
            .get("displayName")
            or item.get("from", {}).get("application", {}).get("displayName")
            or "Unknown"
        )
        created = item.get("createdDateTime")
        if not isinstance(created, str) or not created:
            created = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        body_content = item.get("body", {}).get("content")
        if not isinstance(body_content, str):
            body_content = ""
        message_id = str(item.get("id", ""))
        return {
            "id": message_id,
            "replyToId": item.get("replyToId"),
            "createdDateTime": created,
            "from": {"user": {"displayName": str(sender)}},
            "body": {"content": body_content},
        }

    def _fetch_messages(self, relative_path: str) -> list[dict[str, Any]]:
        url = f"{self.graph_base_url.rstrip('/')}{relative_path}"
        with httpx.Client(timeout=self.timeout_s) as client:
            response = self._execute_with_resilience(
                operation="fetch_messages",
                request_fn=lambda: client.get(url, headers=self._auth_headers()),
            )
        payload = response.json()
        values = payload.get("value", []) if isinstance(payload, dict) else []
        if not isinstance(values, list):
            return []
        normalized = [
            self._normalize_message(item)
            for item in values
            if isinstance(item, dict)
        ]
        return sorted(normalized, key=lambda msg: str(msg.get("createdDateTime", "")))

    def list_messages(self, team_id: str, channel_id: str) -> Iterable[dict[str, Any]]:
        if team_id == "chat":
            path = f"/chats/{channel_id}/messages"
            return self._fetch_messages(path)
        path = f"/teams/{team_id}/channels/{channel_id}/messages"
        return self._fetch_messages(path)

    def stream_thread(self, conversation_id: str) -> Generator[dict[str, Any], None, None]:
        if conversation_id.startswith("chat:"):
            team_id = "chat"
            channel_id = conversation_id.split(":", 1)[1]
        elif ":" in conversation_id:
            team_id, channel_id = conversation_id.split(":", 1)
        else:
            team_id = conversation_id
            channel_id = conversation_id

        seen_ids: set[str] = set()
        polls = max(1, self.stream_polls)
        for idx in range(polls):
            messages = list(self.list_messages(team_id, channel_id))
            for message in messages:
                message_id = str(message.get("id", ""))
                if not message_id or message_id in seen_ids:
                    continue
                seen_ids.add(message_id)
                yield message
            if idx < polls - 1 and self.poll_interval_s > 0:
                time.sleep(self.poll_interval_s)
