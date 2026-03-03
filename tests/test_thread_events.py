from fastapi.testclient import TestClient

from apps.service import main


def test_thread_event_endpoint_accepts_message() -> None:
    with TestClient(main.app) as client:
        res = client.post(
            "/threads/ci_flake/events",
            json={"id": "x", "createdDateTime": "2024-01-01T00:00:00Z"},
        )
        assert res.status_code == 200


def test_thread_event_endpoint_caps_history(monkeypatch) -> None:
    monkeypatch.setenv("OVERHEAROPS_MAX_THREAD_EVENTS", "3")
    main.THREAD_EVENTS.clear()

    with TestClient(main.app) as client:
        for idx in range(5):
            res = client.post(
                "/threads/ci_flake/events",
                json={"id": str(idx), "createdDateTime": "2024-01-01T00:00:00Z"},
            )
            assert res.status_code == 200

    entries = main.THREAD_EVENTS["ci_flake"]
    assert len(entries) == 3
    assert [item["id"] for item in entries] == ["2", "3", "4"]
