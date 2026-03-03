import time
from pathlib import Path

from fastapi.testclient import TestClient

from apps.service import main
from apps.service.queue_store import (
    claim_next_job,
    enqueue_job,
    get_job,
    init_queue,
    requeue_stale_jobs,
)


def test_queue_store_persists_and_requeues_stale_jobs(tmp_path: Path) -> None:
    queue_db = tmp_path / "queue.db"
    init_queue(queue_db)
    enqueue_job(
        queue_db,
        run_id="run-1",
        thread_id="ci_flake",
        tenant_id="default",
        actor="tester",
        payload={"background": True},
    )
    queued = get_job(queue_db, "run-1")
    assert queued is not None
    assert queued["status"] == "queued"

    claimed = claim_next_job(queue_db, worker_id="worker-1", lease_ms=10)
    assert claimed is not None
    assert claimed["run_id"] == "run-1"
    time.sleep(0.02)
    requeued_count = requeue_stale_jobs(queue_db)
    assert requeued_count == 1

    reclaimed = claim_next_job(queue_db, worker_id="worker-2", lease_ms=10)
    assert reclaimed is not None
    assert reclaimed["run_id"] == "run-1"


def test_background_failure_moves_to_dlq_and_replay_succeeds(
    monkeypatch, tmp_path: Path
) -> None:
    main._stop_dispatcher()
    queue_db = tmp_path / "queue.db"
    init_queue(queue_db)
    monkeypatch.setattr(main, "QUEUE_DB", queue_db)
    monkeypatch.setenv("OVERHEAROPS_QUEUE_ENABLED", "true")
    monkeypatch.setenv("OVERHEAROPS_QUEUE_POLL_INTERVAL_S", "0.01")
    monkeypatch.setenv("OVERHEAROPS_QUEUE_LEASE_MS", "200")
    monkeypatch.setenv("OVERHEAROPS_SECURITY_MODE", "off")
    main.RUN_STATUS.clear()
    main.RUN_CANCEL_REQUESTS.clear()

    state = {"failures_left": 1}

    def fake_execute(thread_id: str, run_id: str, tenant_id: str) -> dict[str, object]:
        if state["failures_left"] > 0:
            state["failures_left"] -= 1
            raise RuntimeError("synthetic queue failure")
        return {"run_id": run_id, "verdict": {"action": "approve"}}

    monkeypatch.setattr(main, "_execute_run", fake_execute)

    with TestClient(main.app) as client:
        start = client.post("/runs", json={"thread_id": "ci_flake", "background": True})
        assert start.status_code == 202
        run_id = start.json()["run_id"]

        failed = False
        for _ in range(100):
            status = client.get(f"/runs/{run_id}/status")
            assert status.status_code == 200
            if status.json()["status"] == "failed":
                failed = True
                break
            time.sleep(0.02)
        assert failed

        dlq = client.get("/runs/dlq")
        assert dlq.status_code == 200
        items = dlq.json()["items"]
        assert any(item["run_id"] == run_id for item in items)

        replay = client.post(f"/runs/{run_id}/replay")
        assert replay.status_code == 200
        replay_run_id = replay.json()["run_id"]
        assert replay_run_id != run_id

        succeeded = False
        for _ in range(100):
            status = client.get(f"/runs/{replay_run_id}/status")
            assert status.status_code == 200
            if status.json()["status"] == "succeeded":
                succeeded = True
                break
            time.sleep(0.02)
        assert succeeded
