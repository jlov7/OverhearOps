import time

from fastapi.testclient import TestClient

from apps.service import main


def test_new_run_id_is_unique() -> None:
    first = main._new_run_id("ci_flake", "default")
    second = main._new_run_id("ci_flake", "default")
    assert first != second


def test_runs_endpoint_sync_mode_returns_completed_run() -> None:
    with TestClient(main.app) as client:
        start = client.post("/runs", json={"thread_id": "ci_flake", "background": False})
        assert start.status_code == 200
        payload = start.json()
        assert payload["status"] == "succeeded"

        run_id = payload["run_id"]
        status = client.get(f"/runs/{run_id}/status")
        assert status.status_code == 200
        assert status.json()["status"] == "succeeded"

        run_data = client.get(f"/runs/{run_id}")
        assert run_data.status_code == 200
        assert run_data.json()["run_id"] == run_id


def test_runs_endpoint_background_mode_reaches_terminal_state() -> None:
    with TestClient(main.app) as client:
        start = client.post("/runs", json={"thread_id": "ci_flake", "background": True})
        assert start.status_code == 202
        run_id = start.json()["run_id"]

        terminal = None
        for _ in range(60):
            status = client.get(f"/runs/{run_id}/status")
            assert status.status_code == 200
            state = status.json()["status"]
            if state in {"succeeded", "failed"}:
                terminal = state
                break
            time.sleep(0.02)

        assert terminal == "succeeded"


def test_run_status_recovers_from_status_file() -> None:
    with TestClient(main.app) as client:
        start = client.post("/runs", json={"thread_id": "ci_flake", "background": False})
        assert start.status_code == 200
        run_id = start.json()["run_id"]

        main.RUN_STATUS.clear()
        status = client.get(f"/runs/{run_id}/status")
        assert status.status_code == 200
        assert status.json()["status"] == "succeeded"
