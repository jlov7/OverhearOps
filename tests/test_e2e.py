from fastapi.testclient import TestClient

from apps.service.main import app


def test_run_demo():
    with TestClient(app) as client:
        response = client.post("/run/ci_flake")
        assert response.status_code == 200
        payload = response.json()
        assert "run_id" in payload
        assert payload["verdict"].get("action") in {"approve", "abstain"}
