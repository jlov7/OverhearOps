from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init_queue(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_queue (
                run_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                worker_id TEXT,
                lease_until_ms INTEGER,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_run_queue_status ON run_queue(status, created_at_ms)"
        )


def enqueue_job(
    path: Path,
    run_id: str,
    thread_id: str,
    tenant_id: str,
    actor: str,
    payload: dict[str, Any] | None = None,
) -> None:
    now_ms = int(time.time() * 1000)
    payload_json = json.dumps(payload or {}, sort_keys=True, default=str)
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO run_queue
            (
                run_id,
                thread_id,
                tenant_id,
                actor,
                payload_json,
                status,
                attempts,
                error,
                worker_id,
                lease_until_ms,
                created_at_ms,
                updated_at_ms
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                COALESCE((SELECT attempts FROM run_queue WHERE run_id = ?), 0),
                NULL,
                NULL,
                NULL,
                COALESCE((SELECT created_at_ms FROM run_queue WHERE run_id = ?), ?),
                ?
            )
            """,
            (
                run_id,
                thread_id,
                tenant_id,
                actor,
                payload_json,
                "queued",
                run_id,
                run_id,
                now_ms,
                now_ms,
            ),
        )


def claim_next_job(path: Path, worker_id: str, lease_ms: int = 60_000) -> dict[str, Any] | None:
    now_ms = int(time.time() * 1000)
    with _connect(path) as conn:
        row = conn.execute(
            """
            SELECT run_id, thread_id, tenant_id, actor, payload_json, attempts
            FROM run_queue
            WHERE status = 'queued'
            ORDER BY created_at_ms ASC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None

        run_id = str(row["run_id"])
        updated = conn.execute(
            """
            UPDATE run_queue
            SET status = 'running',
                worker_id = ?,
                lease_until_ms = ?,
                attempts = attempts + 1,
                updated_at_ms = ?
            WHERE run_id = ? AND status = 'queued'
            """,
            (worker_id, now_ms + lease_ms, now_ms, run_id),
        ).rowcount
        if updated != 1:
            return None

        return {
            "run_id": run_id,
            "thread_id": str(row["thread_id"]),
            "tenant_id": str(row["tenant_id"]),
            "actor": str(row["actor"]),
            "payload": json.loads(str(row["payload_json"])),
        }


def complete_job(path: Path, run_id: str, status: str, error: str = "") -> None:
    now_ms = int(time.time() * 1000)
    with _connect(path) as conn:
        conn.execute(
            """
            UPDATE run_queue
            SET status = ?, error = ?, worker_id = NULL, lease_until_ms = NULL, updated_at_ms = ?
            WHERE run_id = ?
            """,
            (status, error, now_ms, run_id),
        )


def requeue_stale_jobs(path: Path) -> int:
    now_ms = int(time.time() * 1000)
    with _connect(path) as conn:
        result = conn.execute(
            """
            UPDATE run_queue
            SET status = 'queued', worker_id = NULL, lease_until_ms = NULL, updated_at_ms = ?
            WHERE status = 'running' AND lease_until_ms IS NOT NULL AND lease_until_ms < ?
            """,
            (now_ms, now_ms),
        )
    return int(result.rowcount)


def get_job(path: Path, run_id: str) -> dict[str, Any] | None:
    with _connect(path) as conn:
        row = conn.execute(
            """
            SELECT
                run_id,
                thread_id,
                tenant_id,
                actor,
                payload_json,
                status,
                attempts,
                error,
                created_at_ms,
                updated_at_ms
            FROM run_queue
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "run_id": str(row["run_id"]),
            "thread_id": str(row["thread_id"]),
            "tenant_id": str(row["tenant_id"]),
            "actor": str(row["actor"]),
            "payload": json.loads(str(row["payload_json"])),
            "status": str(row["status"]),
            "attempts": int(row["attempts"]),
            "error": str(row["error"] or ""),
            "created_at_ms": int(row["created_at_ms"]),
            "updated_at_ms": int(row["updated_at_ms"]),
        }


def replayable_failed_jobs(path: Path) -> list[dict[str, Any]]:
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT run_id, thread_id, tenant_id, actor, payload_json, status, attempts, error
            FROM run_queue
            WHERE status IN ('failed', 'timed_out')
            ORDER BY updated_at_ms DESC
            """
        ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                "run_id": str(row["run_id"]),
                "thread_id": str(row["thread_id"]),
                "tenant_id": str(row["tenant_id"]),
                "actor": str(row["actor"]),
                "payload": json.loads(str(row["payload_json"])),
                "status": str(row["status"]),
                "attempts": int(row["attempts"]),
                "error": str(row["error"] or ""),
            }
        )
    return output


__all__ = [
    "claim_next_job",
    "complete_job",
    "enqueue_job",
    "get_job",
    "init_queue",
    "replayable_failed_jobs",
    "requeue_stale_jobs",
]
