from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

BASE = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

RUNTIME_SETTINGS_PATH = CONFIG_DIR / "runtime_settings.json"
PROMPT_REGISTRY_PATH = CONFIG_DIR / "prompt_registry.json"
POLICY_RULES_PATH = CONFIG_DIR / "policy_rules.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, default=str), encoding="utf-8")


def default_runtime_settings() -> dict[str, Any]:
    return {
        "api_version": "v1",
        "strategy_preset": "safety",
        "feature_flags": {
            "run_execution_enabled": True,
            "ship_side_effects_enabled": True,
            "notifications_enabled": False,
            "analytics_ingest_enabled": True,
        },
        "token_budgets": {
            "per_run": 200000,
            "per_tenant": 50000000,
        },
        "model_routing": {
            "plan": {"model": "gpt-5-mini", "fallback_model": "gpt-5-nano"},
            "judge": {"model": "gpt-5-mini", "fallback_model": "gpt-5-nano"},
            "exec": {"model": "gpt-5-nano", "fallback_model": "gpt-5-nano"},
        },
        "approvals": {
            "min_approvals": 1,
        },
        "notifications": {
            "webhooks": [],
            "teams_webhooks": [],
        },
        "localization": {
            "default_locale": "en",
            "supported_locales": ["en", "es"],
        },
    }


def default_prompt_registry() -> dict[str, Any]:
    return {
        "default_version": "v1",
        "tasks": {
            "plan": {
                "v1": (
                    "Return JSON only. Produce a list of remediation plan objects with keys: "
                    "id, title, hypothesis, steps (array of strings), blast_radius, "
                    "confidence (0..1)."
                ),
                "v2": (
                    "Return JSON only. Produce 2-5 remediation plans with "
                    "id/title/hypothesis/steps/"
                    "blast_radius/confidence and prioritize operational safety."
                ),
            },
            "judge": {
                "v1": (
                    "Return JSON only. Produce an object with keys: "
                    "winner_plan_id, rationale, votes "
                    "(array of objects with persona and plan_id)."
                ),
                "v2": (
                    "Return JSON only. Select a winner_plan_id and explain tradeoffs in rationale; "
                    "votes must include at least three personas."
                ),
            },
        },
    }


def default_policy_rules() -> dict[str, Any]:
    return {
        "simulation": {
            "max_allowed_blast_radius": "medium",
            "require_safety_allowed": True,
        },
        "shipping": {
            "allowed_actions": ["approve", "ship"],
            "min_certainty": 0.66,
        },
    }


def ensure_runtime_files() -> None:
    if not RUNTIME_SETTINGS_PATH.exists():
        _write_json(RUNTIME_SETTINGS_PATH, default_runtime_settings())
    if not PROMPT_REGISTRY_PATH.exists():
        _write_json(PROMPT_REGISTRY_PATH, default_prompt_registry())
    if not POLICY_RULES_PATH.exists():
        _write_json(POLICY_RULES_PATH, default_policy_rules())


def load_runtime_settings() -> dict[str, Any]:
    ensure_runtime_files()
    payload = _read_json(RUNTIME_SETTINGS_PATH)
    if payload is None:
        payload = default_runtime_settings()
    return payload


def save_runtime_settings(payload: dict[str, Any]) -> dict[str, Any]:
    _write_json(RUNTIME_SETTINGS_PATH, payload)
    return load_runtime_settings()


def load_prompt_registry() -> dict[str, Any]:
    ensure_runtime_files()
    payload = _read_json(PROMPT_REGISTRY_PATH)
    if payload is None:
        payload = default_prompt_registry()
    return payload


def save_prompt_registry(payload: dict[str, Any]) -> dict[str, Any]:
    _write_json(PROMPT_REGISTRY_PATH, payload)
    return load_prompt_registry()


def load_policy_rules() -> dict[str, Any]:
    ensure_runtime_files()
    payload = _read_json(POLICY_RULES_PATH)
    if payload is None:
        payload = default_policy_rules()
    return payload


def save_policy_rules(payload: dict[str, Any]) -> dict[str, Any]:
    _write_json(POLICY_RULES_PATH, payload)
    return load_policy_rules()


def get_feature_flag(name: str, default: bool = False) -> bool:
    settings = load_runtime_settings()
    flags = settings.get("feature_flags", {})
    if not isinstance(flags, dict):
        return default
    value = flags.get(name, default)
    return bool(value)


def get_strategy_preset() -> str:
    settings = load_runtime_settings()
    preset = str(settings.get("strategy_preset", "safety")).lower().strip()
    return preset if preset in {"speed", "safety", "cost"} else "safety"


def set_strategy_preset(preset: str) -> str:
    normalized = preset.lower().strip()
    if normalized not in {"speed", "safety", "cost"}:
        raise ValueError("strategy_preset must be one of: speed, safety, cost")
    settings = load_runtime_settings()
    settings["strategy_preset"] = normalized
    save_runtime_settings(settings)
    return normalized


def get_model_for_task(
    task: str,
    default_model: str,
    default_fallback: str | None,
) -> tuple[str, str | None]:
    settings = load_runtime_settings()
    routing = settings.get("model_routing", {})
    if not isinstance(routing, dict):
        return default_model, default_fallback
    task_config = routing.get(task, {})
    if not isinstance(task_config, dict):
        return default_model, default_fallback
    model = str(task_config.get("model", default_model)).strip() or default_model
    fallback_raw = task_config.get("fallback_model", default_fallback)
    fallback = (
        str(fallback_raw).strip()
        if isinstance(fallback_raw, str) and fallback_raw.strip()
        else default_fallback
    )
    return model, fallback


def get_prompt_instruction(task: str, fallback: str) -> str:
    registry = load_prompt_registry()
    default_version = str(registry.get("default_version", "v1"))
    tasks = registry.get("tasks", {})
    if not isinstance(tasks, dict):
        return fallback
    task_versions = tasks.get(task, {})
    if not isinstance(task_versions, dict):
        return fallback
    configured_version = str(task_versions.get("selected_version", default_version))
    chosen = task_versions.get(configured_version)
    if isinstance(chosen, str) and chosen.strip():
        return chosen
    fallback_default = task_versions.get(default_version)
    if isinstance(fallback_default, str) and fallback_default.strip():
        return fallback_default
    return fallback


def get_token_budgets() -> tuple[int, int]:
    env_per_run = os.getenv("OVERHEAROPS_TOKEN_BUDGET_PER_RUN")
    env_per_tenant = os.getenv("OVERHEAROPS_TOKEN_BUDGET_PER_TENANT")
    if env_per_run or env_per_tenant:
        try:
            per_run_env = max(1000, int(env_per_run or "200000"))
        except ValueError:
            per_run_env = 200000
        try:
            per_tenant_env = max(per_run_env, int(env_per_tenant or "50000000"))
        except ValueError:
            per_tenant_env = 50000000
        return per_run_env, per_tenant_env
    settings = load_runtime_settings()
    budgets = settings.get("token_budgets", {})
    if not isinstance(budgets, dict):
        return 200000, 50000000
    try:
        per_run = max(1000, int(budgets.get("per_run", 200000)))
    except (TypeError, ValueError):
        per_run = 200000
    try:
        per_tenant = max(per_run, int(budgets.get("per_tenant", 50000000)))
    except (TypeError, ValueError):
        per_tenant = 50000000
    return per_run, per_tenant


def get_min_approvals() -> int:
    settings = load_runtime_settings()
    approvals = settings.get("approvals", {})
    if not isinstance(approvals, dict):
        return 1
    try:
        return max(1, int(approvals.get("min_approvals", 1)))
    except (TypeError, ValueError):
        return 1


def get_policy_rules() -> dict[str, Any]:
    return load_policy_rules()


__all__ = [
    "ensure_runtime_files",
    "get_feature_flag",
    "get_min_approvals",
    "get_model_for_task",
    "get_policy_rules",
    "get_prompt_instruction",
    "get_strategy_preset",
    "get_token_budgets",
    "load_policy_rules",
    "load_prompt_registry",
    "load_runtime_settings",
    "save_policy_rules",
    "save_prompt_registry",
    "save_runtime_settings",
    "set_strategy_preset",
]
