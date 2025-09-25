"""Simple SQLite-backed checkpoint saver bridging LangGraph and replay needs."""
from __future__ import annotations

import pickle
import sqlite3
import threading
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import RunnableConfig


class SqliteBackedSaver(InMemorySaver):
    """Persists in-memory checkpoints to a SQLite file after each write.

    This is a lightweight approximation until langgraph exposes a built-in
    SQLite saver for 1.0. We inherit the semantics from `InMemorySaver` and add
    durability by storing the internal dictionaries as pickled blobs.
    """

    def __init__(self, path: str | Path):
        super().__init__()
        self.path = Path(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.Lock()
        self._ensure_schema()
        self._load_state()

    def _ensure_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS checkpoints (key TEXT PRIMARY KEY, value BLOB)"
            )

    def _persist(self) -> None:
        payload = {
            "storage": self._to_plain(self.storage),
            "writes": self._to_plain(self.writes),
            "blobs": self._to_plain(self.blobs),
        }
        blob = pickle.dumps(payload)  # noqa: S301 - local persistence
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "REPLACE INTO checkpoints (key, value) VALUES (?, ?)", ("state", blob)
                )

    def _load_state(self) -> None:
        cur = self._conn.cursor()
        cur.execute("SELECT value FROM checkpoints WHERE key = ?", ("state",))
        row = cur.fetchone()
        if row is None:
            return
        payload = pickle.loads(row[0])  # noqa: S301 - local persistence
        self._rehydrate(payload)

    def _to_plain(self, value: Any) -> Any:
        if isinstance(value, defaultdict):
            return {k: self._to_plain(v) for k, v in value.items()}
        if isinstance(value, dict):
            return {k: self._to_plain(v) for k, v in value.items()}
        return value

    def _rehydrate(self, payload: dict) -> None:
        storage = payload.get("storage", {})
        self.storage.clear()
        for thread_id, namespaces in storage.items():
            for ns, checkpoints in namespaces.items():
                self.storage[thread_id][ns] = checkpoints

        writes = payload.get("writes", {})
        self.writes.clear()
        for key, value in writes.items():
            self.writes[key] = value

        blobs = payload.get("blobs", {})
        self.blobs.clear()
        for key, value in blobs.items():
            self.blobs[key] = value

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions,
    ) -> RunnableConfig:
        output = super().put(config, checkpoint, metadata, new_versions)
        self._persist()
        return output

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        super().put_writes(config, writes, task_id, task_path)
        self._persist()

    def delete_thread(self, thread_id: str) -> None:
        super().delete_thread(thread_id)
        self._persist()


__all__ = ["SqliteBackedSaver"]
