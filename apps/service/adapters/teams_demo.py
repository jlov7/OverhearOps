"""Teams-shaped NDJSON adapter for demo replay."""
from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, WebSocket

_DATA_ENV = os.getenv("OVERHEAROPS_DATA_DIR")
_CANDIDATES = [
    Path(_DATA_ENV) if _DATA_ENV else None,
    Path(__file__).resolve().parents[3] / "data" / "demo" / "threads",
    Path(__file__).resolve().parents[2] / ".." / "data" / "demo" / "threads",
    Path.cwd() / "data" / "demo" / "threads",
]

for candidate in _CANDIDATES:
    if candidate and candidate.exists():
        DATA_DIR = candidate.resolve()
        break
else:
    raise FileNotFoundError("Unable to locate demo data directory; set OVERHEAROPS_DATA_DIR")

router = APIRouter(prefix="/demo", tags=["demo"])


def _load_ndjson(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


THREADS: dict[str, list[dict]] = {
    "ci_flake": _load_ndjson(DATA_DIR / "ci_flake.ndjson"),
    "security_alert": _load_ndjson(DATA_DIR / "security_alert.ndjson"),
}


def iter_messages(thread_id: str) -> Iterable[dict]:
    messages = THREADS.get(thread_id)
    if not messages:
        raise KeyError(f"Unknown thread_id={thread_id}")
    return sorted(messages, key=lambda msg: msg.get("createdDateTime", ""))


@router.get("/threads")
def list_threads() -> dict[str, int]:
    """Return available demo threads and their message counts."""

    return {thread_id: len(messages) for thread_id, messages in THREADS.items()}


@router.websocket("/stream/{thread_id}")
async def stream_thread(websocket: WebSocket, thread_id: str) -> None:
    await websocket.accept()
    try:
        for message in iter_messages(thread_id):
            await websocket.send_json(message)
    finally:
        await websocket.close()


def first_message_time(thread_id: str) -> datetime:
    entry = next(iter(iter_messages(thread_id)))
    return datetime.fromisoformat(entry["createdDateTime"].replace("Z", "+00:00"))


__all__ = ["router", "iter_messages", "list_threads", "first_message_time"]
