from typing import Any

import httpx
import pytest

from apps.service.adapters.teams_graph import TeamsGraphAdapter


class FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "failure",
                request=httpx.Request("GET", "https://graph.microsoft.com/v1.0/chats/chat/messages"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict[str, object]:
        return self._payload


def _configure_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MS_TENANT_ID", "tenant-1")
    monkeypatch.setenv("MS_CLIENT_ID", "client-1")
    monkeypatch.setenv("MS_CLIENT_SECRET", "secret-1")


def test_graph_adapter_fetches_channel_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_creds(monkeypatch)

    calls: dict[str, list[str]] = {"post": [], "get": []}

    def fake_post(self, url: str, data: dict[str, str]) -> FakeResponse:
        calls["post"].append(url)
        assert data["grant_type"] == "client_credentials"
        return FakeResponse({"access_token": "token-1", "expires_in": 3600})

    def fake_get(self, url: str, headers: dict[str, str]) -> FakeResponse:
        calls["get"].append(url)
        assert headers["Authorization"] == "Bearer token-1"
        return FakeResponse(
            {
                "value": [
                    {
                        "id": "msg-1",
                        "createdDateTime": "2024-01-01T00:00:00Z",
                        "replyToId": None,
                        "from": {"user": {"displayName": "Ada"}},
                        "body": {"content": "CI failed on windows"},
                    }
                ]
            }
        )

    monkeypatch.setattr("httpx.Client.post", fake_post)
    monkeypatch.setattr("httpx.Client.get", fake_get)

    adapter = TeamsGraphAdapter()
    messages = list(adapter.list_messages("team-1", "general"))
    assert len(messages) == 1
    assert messages[0]["id"] == "msg-1"
    assert messages[0]["from"]["user"]["displayName"] == "Ada"
    assert "/teams/team-1/channels/general/messages" in calls["get"][0]


def test_graph_adapter_fetches_chat_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_creds(monkeypatch)

    def fake_post(self, url: str, data: dict[str, str]) -> FakeResponse:
        return FakeResponse({"access_token": "token-1", "expires_in": 3600})

    def fake_get(self, url: str, headers: dict[str, str]) -> FakeResponse:
        assert "/chats/chat-123/messages" in url
        return FakeResponse({"value": []})

    monkeypatch.setattr("httpx.Client.post", fake_post)
    monkeypatch.setattr("httpx.Client.get", fake_get)

    adapter = TeamsGraphAdapter()
    messages = list(adapter.list_messages("chat", "chat-123"))
    assert messages == []


def test_graph_adapter_stream_thread_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_creds(monkeypatch)
    monkeypatch.setenv("OVERHEAROPS_GRAPH_STREAM_POLLS", "2")
    monkeypatch.setenv("OVERHEAROPS_GRAPH_POLL_INTERVAL_S", "0")

    adapter = TeamsGraphAdapter()
    first = [
        {
            "id": "a",
            "createdDateTime": "2024-01-01T00:00:00Z",
            "replyToId": None,
            "from": {"user": {"displayName": "Ada"}},
            "body": {"content": "one"},
        }
    ]
    second: list[dict[str, Any]] = [
        *first,
        {
            "id": "b",
            "createdDateTime": "2024-01-01T00:00:01Z",
            "replyToId": "a",
            "from": {"user": {"displayName": "Grace"}},
            "body": {"content": "two"},
        },
    ]
    sequence: list[list[dict[str, Any]]] = [first, second]
    state = {"idx": 0}

    def fake_list(team_id: str, channel_id: str) -> list[dict[str, object]]:
        assert team_id == "chat"
        assert channel_id == "chat-123"
        idx = state["idx"]
        state["idx"] = min(state["idx"] + 1, len(sequence) - 1)
        return sequence[idx]

    monkeypatch.setattr(adapter, "list_messages", fake_list)
    emitted = list(adapter.stream_thread("chat:chat-123"))
    assert [msg["id"] for msg in emitted] == ["a", "b"]


def test_graph_adapter_prod_credential_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OVERHEAROPS_CREDENTIAL_SCOPE", "prod")
    monkeypatch.setenv("MS_PROD_TENANT_ID", "prod-tenant")
    monkeypatch.setenv("MS_PROD_CLIENT_ID", "prod-client")
    monkeypatch.setenv("MS_PROD_CLIENT_SECRET", "prod-secret")

    def fake_post(self, url: str, data: dict[str, str]) -> FakeResponse:
        assert data["client_id"] == "prod-client"
        return FakeResponse({"access_token": "token-1", "expires_in": 3600})

    def fake_get(self, url: str, headers: dict[str, str]) -> FakeResponse:
        return FakeResponse({"value": []})

    monkeypatch.setattr("httpx.Client.post", fake_post)
    monkeypatch.setattr("httpx.Client.get", fake_get)

    adapter = TeamsGraphAdapter()
    assert list(adapter.list_messages("chat", "chat-123")) == []


def test_graph_adapter_retries_retryable_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_creds(monkeypatch)
    monkeypatch.setenv("OVERHEAROPS_EXTERNAL_MAX_RETRIES", "1")
    monkeypatch.setenv("OVERHEAROPS_EXTERNAL_RETRY_BACKOFF_S", "0")

    attempts = {"get": 0}

    def fake_post(self, url: str, data: dict[str, str]) -> FakeResponse:
        return FakeResponse({"access_token": "token-1", "expires_in": 3600})

    def fake_get(self, url: str, headers: dict[str, str]) -> FakeResponse:
        attempts["get"] += 1
        if attempts["get"] == 1:
            return FakeResponse({}, status_code=429)
        return FakeResponse({"value": []})

    monkeypatch.setattr("httpx.Client.post", fake_post)
    monkeypatch.setattr("httpx.Client.get", fake_get)

    adapter = TeamsGraphAdapter()
    messages = list(adapter.list_messages("chat", "chat-123"))
    assert messages == []
    assert attempts["get"] == 2


def test_graph_adapter_circuit_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_creds(monkeypatch)
    monkeypatch.setenv("OVERHEAROPS_EXTERNAL_MAX_RETRIES", "0")
    monkeypatch.setenv("OVERHEAROPS_EXTERNAL_CIRCUIT_FAILURES", "1")
    monkeypatch.setenv("OVERHEAROPS_EXTERNAL_CIRCUIT_COOLDOWN_S", "60")

    attempts = {"get": 0}

    def fake_post(self, url: str, data: dict[str, str]) -> FakeResponse:
        return FakeResponse({"access_token": "token-1", "expires_in": 3600})

    def fake_get(self, url: str, headers: dict[str, str]) -> FakeResponse:
        attempts["get"] += 1
        return FakeResponse({}, status_code=500)

    monkeypatch.setattr("httpx.Client.post", fake_post)
    monkeypatch.setattr("httpx.Client.get", fake_get)

    adapter = TeamsGraphAdapter()
    with pytest.raises(RuntimeError, match="failed after retries"):
        list(adapter.list_messages("chat", "chat-123"))
    with pytest.raises(RuntimeError, match="circuit breaker open"):
        list(adapter.list_messages("chat", "chat-123"))
    assert attempts["get"] == 1
