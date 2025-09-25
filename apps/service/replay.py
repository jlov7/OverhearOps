"""ARE-style replay scheduler for Teams NDJSON threads."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import httpx

from .adapters.teams_demo import iter_messages


@dataclass
class ScheduledMessage:
    message: dict
    delay: float


class ReplayScheduler:
    def __init__(
        self,
        thread_id: str,
        speed: float = 1.0,
        jitter: float = 0.1,
        seed: int | None = None,
    ):
        self.thread_id = thread_id
        self.speed = speed
        self.jitter = jitter
        self.rng = random.Random(seed)  # noqa: S311 - deterministic demo RNG

    @staticmethod
    def _parse_ts(timestamp: str) -> datetime:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def build_schedule(self) -> list[ScheduledMessage]:
        messages = list(iter_messages(self.thread_id))
        schedule: list[ScheduledMessage] = []
        previous_ts: datetime | None = None
        for message in messages:
            current_ts = self._parse_ts(message["createdDateTime"])
            base_delay = 0.0 if previous_ts is None else (current_ts - previous_ts).total_seconds()
            previous_ts = current_ts
            jitter = base_delay * self.jitter * self.rng.uniform(-1, 1)
            adjusted = base_delay + jitter
            delay = 0.0 if self.speed <= 0 else max(0.0, adjusted / self.speed)
            schedule.append(ScheduledMessage(message=message, delay=delay))
        return schedule

    def schedule_hash(self, schedule: Iterable[ScheduledMessage]) -> str:
        digest = hashlib.sha256()
        for item in schedule:
            digest.update(item.message["id"].encode())
            digest.update(f"{item.delay:.6f}".encode())
        return digest.hexdigest()


async def replay(
    scheduler: ReplayScheduler,
    push_endpoint: str | None = None,
    run_after: bool = False,
) -> tuple[list[ScheduledMessage], str, str | None]:
    schedule = scheduler.build_schedule()
    schedule_hash = scheduler.schedule_hash(schedule)
    client: httpx.AsyncClient | None = None
    try:
        if push_endpoint:
            client = httpx.AsyncClient(base_url=push_endpoint, timeout=10)
        for item in schedule:
            if item.delay > 0:
                await asyncio.sleep(item.delay)
            if client is None:
                print(json.dumps(item.message))
            else:
                await client.post(f"/api/thread/{scheduler.thread_id}/events", json=item.message)
        run_id = None
        if run_after and client is not None:
            response = await client.post(f"/api/run/{scheduler.thread_id}")
            response.raise_for_status()
            run_id = response.json()["run_id"]
        return schedule, schedule_hash, run_id
    finally:
        if client is not None:
            await client.aclose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Teams NDJSON thread with jitter")
    parser.add_argument("--thread", default="ci_flake", help="Thread identifier")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speed multiplier (1.0 = realtime)",
    )
    parser.add_argument("--jitter", type=float, default=0.1, help="Relative jitter fraction (±)")
    parser.add_argument("--seed", type=int, default=None, help="Seed for determinism")
    parser.add_argument("--endpoint", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--push", action="store_true", help="Push events to backend endpoint")
    parser.add_argument("--trigger-run", action="store_true", help="Trigger agent run after replay")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scheduler = ReplayScheduler(args.thread, speed=args.speed, jitter=args.jitter, seed=args.seed)
    push_endpoint = args.endpoint if args.push or args.trigger_run else None
    schedule, schedule_hash, run_id = asyncio.run(
        replay(scheduler, push_endpoint, run_after=args.trigger_run)
    )
    print(
        json.dumps(
            {
                "thread": args.thread,
                "events": len(schedule),
                "hash": schedule_hash,
                "run_id": run_id,
            }
        )
    )


if __name__ == "__main__":
    main()
