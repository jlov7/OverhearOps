import json
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient

from apps.service.main import app
from apps.service.runtime_config import (
    POLICY_RULES_PATH,
    PROMPT_REGISTRY_PATH,
    RUNTIME_SETTINGS_PATH,
)


def _read(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_run_history_compare_export_endpoints() -> None:
    with TestClient(app) as client:
        first = client.post("/runs", json={"thread_id": "ci_flake", "background": False})
        second = client.post("/runs", json={"thread_id": "security_alert", "background": False})
        assert first.status_code == 200
        assert second.status_code == 200

        run_a = first.json()["run_id"]
        run_b = second.json()["run_id"]

        history = client.get("/runs/history")
        assert history.status_code == 200
        assert history.json()["count"] >= 2

        comparison = client.get("/runs/compare", params={"left": run_a, "right": run_b})
        assert comparison.status_code == 200
        assert "diff" in comparison.json()

        exported = client.get("/runs/export", params={"format": "jsonl"})
        assert exported.status_code == 200
        assert run_a in exported.text


def test_admin_settings_and_strategy_roundtrip() -> None:
    original = _read(RUNTIME_SETTINGS_PATH)
    try:
        with TestClient(app) as client:
            settings = client.get("/admin/settings")
            assert settings.status_code == 200
            payload = settings.json()
            payload["feature_flags"]["run_execution_enabled"] = True
            payload["approvals"]["min_approvals"] = 2
            updated = client.put("/admin/settings", json={"payload": payload})
            assert updated.status_code == 200
            assert updated.json()["approvals"]["min_approvals"] == 2

            strategy = client.post("/admin/strategy/cost")
            assert strategy.status_code == 200
            assert strategy.json()["strategy_preset"] == "cost"
    finally:
        _write(RUNTIME_SETTINGS_PATH, original)


def test_simulation_endpoint_uses_policy_rules() -> None:
    original_policy = _read(POLICY_RULES_PATH)
    try:
        policy = json.loads(json.dumps(original_policy))
        policy["shipping"]["min_certainty"] = 0.99
        _write(POLICY_RULES_PATH, policy)

        with TestClient(app) as client:
            start = client.post("/runs", json={"thread_id": "ci_flake", "background": False})
            assert start.status_code == 200
            run_id = start.json()["run_id"]
            simulated = client.post(f"/runs/{run_id}/simulate")
            assert simulated.status_code == 200
            assert "checks" in simulated.json()
    finally:
        _write(POLICY_RULES_PATH, original_policy)


def test_usage_endpoint_returns_tenant_usage() -> None:
    with TestClient(app) as client:
        client.post("/runs", json={"thread_id": "ci_flake", "background": False})
        usage = client.get("/tenants/default/usage")
        assert usage.status_code == 200
        assert usage.json()["used_tokens"] >= 0


def test_run_execution_flag_can_disable_runs() -> None:
    original = _read(RUNTIME_SETTINGS_PATH)
    try:
        payload = json.loads(json.dumps(original))
        payload["feature_flags"]["run_execution_enabled"] = False
        _write(RUNTIME_SETTINGS_PATH, payload)
        with TestClient(app) as client:
            blocked = client.post("/runs", json={"thread_id": "ci_flake", "background": False})
            assert blocked.status_code == 503
    finally:
        _write(RUNTIME_SETTINGS_PATH, original)


def test_prompt_registry_admin_endpoints() -> None:
    original = _read(PROMPT_REGISTRY_PATH)
    try:
        with TestClient(app) as client:
            prompts = client.get("/admin/prompts")
            assert prompts.status_code == 200
            payload = prompts.json()
            payload["tasks"]["plan"]["selected_version"] = "v2"
            updated = client.put("/admin/prompts", json={"payload": payload})
            assert updated.status_code == 200
            assert updated.json()["tasks"]["plan"]["selected_version"] == "v2"
    finally:
        _write(PROMPT_REGISTRY_PATH, original)
