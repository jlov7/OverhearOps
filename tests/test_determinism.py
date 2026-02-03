import shutil

from fastapi.testclient import TestClient

from apps.service import main


def test_determinism_offline(monkeypatch):
    values = [1000.0, 1001.0]
    calls = {"count": 0}

    def fake_time() -> float:
        idx = calls["count"]
        calls["count"] += 1
        if idx < len(values):
            return values[idx]
        return values[-1]

    for value in values:
        run_id = f"{main.ADAPTER_MODE}-ci_flake-{int(value)}"
        target = main.RUNS / run_id
        if target.exists():
            shutil.rmtree(target)

    monkeypatch.setattr(main.time, "time", fake_time)

    with TestClient(main.app) as client:
        run1 = client.post("/run/ci_flake").json()["run_id"]
        run2 = client.post("/run/ci_flake").json()["run_id"]
        data1 = client.get(f"/runs/{run1}").json()
        data2 = client.get(f"/runs/{run2}").json()

    assert data1["replay_hash"] == data2["replay_hash"]
    assert data1["artefacts_by_plan"] == data2["artefacts_by_plan"]
