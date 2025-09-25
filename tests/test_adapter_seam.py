from fastapi.testclient import TestClient

from apps.service import main


def test_demo_adapter_mode(monkeypatch):
    monkeypatch.setattr(main, "ADAPTER_MODE", "demo")
    monkeypatch.setattr(main, "_GRAPH_ADAPTER", None)
    monkeypatch.delenv("MS_TENANT_ID", raising=False)
    monkeypatch.delenv("MS_CLIENT_ID", raising=False)
    monkeypatch.delenv("MS_CLIENT_SECRET", raising=False)

    with TestClient(main.app) as client:
        response = client.post("/run/ci_flake")
        assert response.status_code == 200
        payload = response.json()
        assert payload["run_id"].startswith("demo-ci_flake-")


def test_playground_mode_card(monkeypatch):
    monkeypatch.setattr(main, "ADAPTER_MODE", "playground")
    monkeypatch.setattr(main, "_GRAPH_ADAPTER", None)

    with TestClient(main.app) as client:
        card_response = client.get("/playground/card/plan")
        assert card_response.status_code == 200
        card = card_response.json()
        assert card["version"] == "1.5"
        assert card["body"][0]["text"] == "OverhearOps Plan B"

        run_response = client.post("/run/ci_flake")
        assert run_response.status_code == 200
        assert run_response.json()["run_id"].startswith("playground-ci_flake-")


def test_graph_mode_needs_credentials(monkeypatch):
    monkeypatch.setattr(main, "ADAPTER_MODE", "graph")
    monkeypatch.setattr(main, "_GRAPH_ADAPTER", None)
    monkeypatch.delenv("MS_TENANT_ID", raising=False)
    monkeypatch.delenv("MS_CLIENT_ID", raising=False)
    monkeypatch.delenv("MS_CLIENT_SECRET", raising=False)

    with TestClient(main.app) as client:
        response = client.post("/run/team:general")
        assert response.status_code == 401
        detail = response.json().get("detail", "")
        assert "not configured" in detail.lower()
