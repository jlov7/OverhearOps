from fastapi.testclient import TestClient

from apps.service.main import app


def test_eval_ci_flake_run_shape() -> None:
    with TestClient(app) as client:
        response = client.post("/runs", json={"thread_id": "ci_flake", "background": False})
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] in {"succeeded", "failed", "timed_out"}
        assert "run_id" in payload


def test_eval_security_alert_run_shape() -> None:
    with TestClient(app) as client:
        response = client.post("/runs", json={"thread_id": "security_alert", "background": False})
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] in {"succeeded", "failed", "timed_out"}
        assert "run_id" in payload
