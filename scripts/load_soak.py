#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def _worker(client: httpx.AsyncClient, base_url: str, requests: int) -> list[float]:
    durations: list[float] = []
    for _ in range(requests):
        start = time.perf_counter()
        response = await client.get(f"{base_url}/health")
        response.raise_for_status()
        durations.append(time.perf_counter() - start)
    return durations


async def run_load(base_url: str, concurrency: int, requests_per_worker: int) -> int:
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [
            _worker(client, base_url, requests_per_worker)
            for _ in range(concurrency)
        ]
        results = await asyncio.gather(*tasks)
    durations = [value for batch in results for value in batch]
    p95 = sorted(durations)[max(0, int(len(durations) * 0.95) - 1)]
    print(
        "load_summary",
        {
            "requests": len(durations),
            "avg_ms": round(statistics.mean(durations) * 1000, 2),
            "p95_ms": round(p95 * 1000, 2),
        },
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run basic OverhearOps HTTP load/soak checks.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests-per-worker", type=int, default=50)
    args = parser.parse_args()
    return asyncio.run(
        run_load(
            base_url=args.base_url.rstrip("/"),
            concurrency=max(1, args.concurrency),
            requests_per_worker=max(1, args.requests_per_worker),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
