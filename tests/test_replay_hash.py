from fastapi.testclient import TestClient

from apps.service.main import RUNS, app


def _read_hash(run_id: str) -> str:
    return (RUNS / run_id / "hash.txt").read_text(encoding="utf-8").strip()


def test_replay_hash_deterministic():
    with TestClient(app) as client:
        first = client.post("/run/ci_flake")
        second = client.post("/run/ci_flake")
        assert first.status_code == 200
        assert second.status_code == 200
        first_id = first.json()["run_id"]
        second_id = second.json()["run_id"]

    first_hash = _read_hash(first_id)
    second_hash = _read_hash(second_id)

    assert first_hash
    assert first_hash == second_hash
