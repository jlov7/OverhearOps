#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from urllib.parse import urlparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Check public OverhearOps status probes.")
    parser.add_argument("--api-base", default="http://localhost:8000")
    args = parser.parse_args()

    base = args.api_base.rstrip("/")
    urls = [f"{base}/livez", f"{base}/readyz", f"{base}/status/public"]
    results: dict[str, object] = {}
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Invalid URL scheme")
        req = urllib.request.Request(url=url, method="GET")  # noqa: S310
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            results[url] = json.loads(resp.read().decode("utf-8"))
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
