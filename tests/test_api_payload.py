from fastapi.testclient import TestClient

from apps.service.main import app


def test_run_payload_shape():
    with TestClient(app) as client:
        res = client.post("/run/ci_flake")
        assert res.status_code == 200
        run_id = res.json()["run_id"]
        data = client.get(f"/runs/{run_id}").json()
        assert "plans" in data
        assert "artefacts_by_plan" in data
        assert "verdict" in data
        assert "gate" in data
