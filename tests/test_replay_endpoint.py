from fastapi.testclient import TestClient

from apps.service.main import app


def test_thread_event_endpoint_accepts_message():
    with TestClient(app) as client:
        res = client.post(
            "/threads/ci_flake/events",
            json={"id": "x", "createdDateTime": "2024-01-01T00:00:00Z"},
        )
        assert res.status_code == 200
