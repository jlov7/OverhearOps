from fastapi.testclient import TestClient

from apps.service.main import app


def test_security_thread_uses_security_fixtures():
    with TestClient(app) as client:
        run = client.post("/run/security_alert")
        assert run.status_code == 200
        run_id = run.json()["run_id"]
        data = client.get(f"/runs/{run_id}").json()

    assert data["plans"][0]["id"] == "plan-rotate-keys"
