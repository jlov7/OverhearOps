from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast

BASE = Path(__file__).resolve().parents[2]
RUNS = BASE / "runs"
USAGE_DIR = RUNS / "usage"
USAGE_DIR.mkdir(parents=True, exist_ok=True)


def _tenant_usage_path(tenant_id: str) -> Path:
    return USAGE_DIR / f"{tenant_id}.json"


def _read_usage(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "tenant_id": path.stem,
            "used_tokens": 0,
            "runs": 0,
            "events": [],
        }
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    return payload


def get_tenant_usage(tenant_id: str) -> dict[str, Any]:
    return _read_usage(_tenant_usage_path(tenant_id))


def record_usage(
    tenant_id: str,
    run_id: str,
    token_cost: int,
    cost_usd: float = 0.0,
) -> dict[str, Any]:
    path = _tenant_usage_path(tenant_id)
    usage = _read_usage(path)
    usage["used_tokens"] = int(usage.get("used_tokens", 0)) + max(0, token_cost)
    usage["runs"] = int(usage.get("runs", 0)) + 1
    events = usage.get("events", [])
    if not isinstance(events, list):
        events = []
    events.append(
        {
            "run_id": run_id,
            "token_cost": max(0, token_cost),
            "cost_usd": round(max(0.0, cost_usd), 6),
            "ts_ms": int(time.time() * 1000),
        }
    )
    usage["events"] = events[-1000:]
    path.write_text(json.dumps(usage, sort_keys=True, indent=2, default=str), encoding="utf-8")
    return usage


def export_usage_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(USAGE_DIR.glob("*.json")):
        records.append(_read_usage(path))
    return records


__all__ = ["export_usage_records", "get_tenant_usage", "record_usage"]
