#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from urllib.parse import urlparse


def _request(
    method: str,
    url: str,
    token: str,
    tenant: str,
) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("api-base must use http or https")
    req = urllib.request.Request(url=url, method=method)  # noqa: S310
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-OverhearOps-Tenant", tenant)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        payload = resp.read().decode("utf-8")
    parsed_payload = json.loads(payload)
    if not isinstance(parsed_payload, dict):
        raise ValueError("Expected JSON object response from API")
    return parsed_payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List and replay failed OverhearOps jobs from DLQ."
    )
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--token", required=True, help="Bearer token for operator role")
    parser.add_argument("--tenant", default="default")
    parser.add_argument("--run-id", help="Replay a specific failed run id")
    args = parser.parse_args()

    api = args.api_base.rstrip("/")
    if args.run_id:
        payload = _request(
            method="POST",
            url=f"{api}/runs/{args.run_id}/replay",
            token=args.token,
            tenant=args.tenant,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    payload = _request(
        method="GET",
        url=f"{api}/runs/dlq",
        token=args.token,
        tenant=args.tenant,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
