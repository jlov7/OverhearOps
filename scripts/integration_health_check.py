#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from urllib.parse import urlparse


def _get_json(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must use http/https")
    req = urllib.request.Request(url=url, method="GET")  # noqa: S310
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Integration health monitor for OverhearOps dependencies."
    )
    parser.add_argument("--api-base", default="http://localhost:8000")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    report: dict[str, object] = {
        "api_health": "unknown",
        "public_status": "unknown",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "graph_credentials_configured": all(
            [
                os.getenv("MS_DRYRUN_TENANT_ID") or os.getenv("MS_TENANT_ID"),
                os.getenv("MS_DRYRUN_CLIENT_ID") or os.getenv("MS_CLIENT_ID"),
                os.getenv("MS_DRYRUN_CLIENT_SECRET") or os.getenv("MS_CLIENT_SECRET"),
            ]
        ),
    }

    try:
        health = _get_json(f"{api_base}/health")
        report["api_health"] = health.get("status", "unknown")
    except Exception as exc:  # noqa: BLE001
        report["api_health"] = f"error: {exc}"

    try:
        status = _get_json(f"{api_base}/status/public")
        report["public_status"] = status.get("status", "unknown")
        report["dlq_items"] = status.get("dlq_items", 0)
    except Exception as exc:  # noqa: BLE001
        report["public_status"] = f"error: {exc}"

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["api_health"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
