import hmac
import json
import time
from hashlib import sha256
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.service import main


def _set_security_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OVERHEAROPS_SECURITY_MODE", "api_key")
    monkeypatch.setenv("OVERHEAROPS_DEFAULT_TENANT", "tenant_a")
    monkeypatch.setenv(
        "OVERHEAROPS_AUTH_TOKENS_JSON",
        json.dumps(
            {
                "token-operator-a": {
                    "role": "operator",
                    "tenant_id": "tenant_a",
                    "subject": "operator-a",
                },
                "token-viewer-a": {
                    "role": "viewer",
                    "tenant_id": "tenant_a",
                    "subject": "viewer-a",
                },
                "token-viewer-b": {
                    "role": "viewer",
                    "tenant_id": "tenant_b",
                    "subject": "viewer-b",
                },
                "token-approver-a": {
                    "role": "approver",
                    "tenant_id": "tenant_a",
                    "subject": "approver-a",
                },
                "token-approver-a2": {
                    "role": "approver",
                    "tenant_id": "tenant_a",
                    "subject": "approver-a2",
                },
                "token-admin": {
                    "role": "admin",
                    "tenant_id": "tenant_a",
                    "subject": "admin-user",
                },
            }
        ),
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_security_mode_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_security_tokens(monkeypatch)
    with TestClient(main.app) as client:
        response = client.get("/threads")
        assert response.status_code == 401


def test_role_guard_rejects_viewer_run_start(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_security_tokens(monkeypatch)
    with TestClient(main.app) as client:
        response = client.post(
            "/runs",
            json={"thread_id": "ci_flake", "background": False},
            headers=_auth("token-viewer-a"),
        )
        assert response.status_code == 403


def test_tenant_isolation_blocks_cross_tenant_read(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_security_tokens(monkeypatch)
    with TestClient(main.app) as client:
        start = client.post(
            "/runs",
            json={"thread_id": "ci_flake", "background": False},
            headers=_auth("token-operator-a"),
        )
        assert start.status_code == 200
        run_id = start.json()["run_id"]

        forbidden = client.get(
            f"/runs/{run_id}",
            headers={**_auth("token-viewer-b"), "X-OverhearOps-Tenant": "tenant_b"},
        )
        assert forbidden.status_code == 404


def test_runs_idempotency_returns_existing_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_security_tokens(monkeypatch)
    with TestClient(main.app) as client:
        headers = {**_auth("token-operator-a"), "Idempotency-Key": "same-run"}
        first = client.post(
            "/runs",
            json={"thread_id": "ci_flake", "background": False},
            headers=headers,
        )
        second = client.post(
            "/runs",
            json={"thread_id": "ci_flake", "background": False},
            headers=headers,
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["run_id"] == second.json()["run_id"]


def test_run_cancel_endpoint_sets_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_security_tokens(monkeypatch)
    main.RUN_STATUS.clear()
    main.RUN_CANCEL_REQUESTS.clear()

    def fake_execute(thread_id: str, run_id: str, tenant_id: str) -> dict[str, Any]:
        time.sleep(0.2)
        return {"run_id": run_id, "verdict": {}}

    monkeypatch.setattr(main, "_execute_run", fake_execute)

    with TestClient(main.app) as client:
        start = client.post(
            "/runs",
            json={"thread_id": "ci_flake", "background": True},
            headers=_auth("token-operator-a"),
        )
        assert start.status_code == 202
        run_id = start.json()["run_id"]

        cancel = client.post(f"/runs/{run_id}/cancel", headers=_auth("token-operator-a"))
        assert cancel.status_code == 200

        status = None
        for _ in range(40):
            poll = client.get(f"/runs/{run_id}/status", headers=_auth("token-operator-a"))
            assert poll.status_code == 200
            status = poll.json()["status"]
            if status in {"cancelled", "failed", "succeeded"}:
                break
            time.sleep(0.02)

        assert status == "cancelled"


def test_run_timeout_transitions_to_timed_out(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_security_tokens(monkeypatch)
    monkeypatch.setenv("OVERHEAROPS_RUN_MAX_RUNTIME_S", "1")

    def fake_execute(thread_id: str, run_id: str, tenant_id: str) -> dict[str, Any]:
        time.sleep(1.2)
        return {"run_id": run_id, "verdict": {}}

    monkeypatch.setattr(main, "_execute_run", fake_execute)

    with TestClient(main.app) as client:
        start = client.post(
            "/runs",
            json={"thread_id": "ci_flake", "background": False},
            headers=_auth("token-operator-a"),
        )
        assert start.status_code == 500
        assert start.json()["status"] == "timed_out"


def test_ingest_signature_and_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OVERHEAROPS_SECURITY_MODE", "off")
    monkeypatch.setenv("OVERHEAROPS_INGEST_HMAC_SECRET", "topsecret")
    main.THREAD_EVENTS.clear()

    payload = {
        "id": "evt-1",
        "createdDateTime": "2024-01-01T00:00:00Z",
        "body": {"content": "Contact dev@example.com token=abc12345"},
    }
    raw = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"topsecret", raw, sha256).hexdigest()

    with TestClient(main.app) as client:
        missing = client.post("/threads/ci_flake/events", json=payload)
        assert missing.status_code == 401

        accepted = client.post(
            "/threads/ci_flake/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-OverhearOps-Signature": f"sha256={signature}",
            },
        )
        assert accepted.status_code == 200

    stored = main.THREAD_EVENTS["ci_flake"][0]
    body = stored["body"]["content"]
    assert "[REDACTED_EMAIL]" in body
    assert "[REDACTED]" in body


def test_ship_requires_approval_and_live_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_security_tokens(monkeypatch)
    monkeypatch.setenv("OVERHEAROPS_REQUIRE_APPROVAL_FOR_SHIP", "true")
    monkeypatch.setenv("OVERHEAROPS_INTEGRATION_MODE", "dry_run")
    settings_path = main.BASE / "config" / "runtime_settings.json"
    original_settings = settings_path.read_text(encoding="utf-8")
    settings = json.loads(original_settings)
    settings["approvals"]["min_approvals"] = 2
    settings_path.write_text(json.dumps(settings, indent=2, sort_keys=True), encoding="utf-8")

    try:
        with TestClient(main.app) as client:
            start = client.post(
                "/runs",
                json={"thread_id": "ci_flake", "background": False},
                headers=_auth("token-operator-a"),
            )
            assert start.status_code == 200
            run_id = start.json()["run_id"]

            dry_run_ship = client.post(f"/runs/{run_id}/ship", headers=_auth("token-operator-a"))
            assert dry_run_ship.status_code == 409
            assert "dry_run" in dry_run_ship.json()["detail"]

            monkeypatch.setenv("OVERHEAROPS_INTEGRATION_MODE", "live")
            missing_approval = client.post(
                f"/runs/{run_id}/ship",
                headers=_auth("token-operator-a"),
            )
            assert missing_approval.status_code == 409
            assert "approver sign-off" in missing_approval.json()["detail"]

            approve = client.post(
                f"/runs/{run_id}/approve",
                json={"note": "ship approved"},
                headers=_auth("token-approver-a"),
            )
            assert approve.status_code == 200
            blocked_on_quorum = client.post(
                f"/runs/{run_id}/ship",
                headers=_auth("token-operator-a"),
            )
            assert blocked_on_quorum.status_code == 409
            assert "additional approvers" in blocked_on_quorum.json()["detail"]

            approve_2 = client.post(
                f"/runs/{run_id}/approve",
                json={"note": "second approval"},
                headers=_auth("token-approver-a2"),
            )
            assert approve_2.status_code == 200

            shipped = client.post(f"/runs/{run_id}/ship", headers=_auth("token-operator-a"))
            assert shipped.status_code == 200
            assert shipped.json()["applied"] is True
            assert shipped.json()["integration_mode"] == "live"
    finally:
        settings_path.write_text(original_settings, encoding="utf-8")


def test_dsr_export_and_delete_skeleton(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_security_tokens(monkeypatch)
    with TestClient(main.app) as client:
        start = client.post(
            "/runs",
            json={"thread_id": "ci_flake", "background": False},
            headers=_auth("token-operator-a"),
        )
        assert start.status_code == 200

        exported = client.get(
            "/tenants/tenant_a/dsr/export",
            headers={**_auth("token-admin"), "X-OverhearOps-Tenant": "tenant_a"},
        )
        assert exported.status_code == 200
        assert exported.json()["count"] >= 1

        dry_deleted = client.post(
            "/tenants/tenant_a/dsr/delete",
            json={"dry_run": True},
            headers={**_auth("token-admin"), "X-OverhearOps-Tenant": "tenant_a"},
        )
        assert dry_deleted.status_code == 200
        assert dry_deleted.json()["dry_run"] is True
