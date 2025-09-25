from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

import orjson
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace

from packages.agentkit.graph import build_graph
from packages.obs.action_graph import build_graphs
from packages.obs.otel import init_otel


def _spans_path(run_id: str) -> Path:
    return RUNS / run_id / 'spans.jsonl'


def _compute_replay_hash(run_id: str) -> str:
    digest = hashlib.sha256()
    span_file = _spans_path(run_id)
    if not span_file.exists():
        digest.update(run_id.encode('utf-8'))
        return digest.hexdigest()
    records: list[tuple[str, str, str, str]] = []
    with span_file.open('r', encoding='utf-8') as handle:
        for line in handle:
            data = json.loads(line)
            records.append(
                (
                    str(data.get('span_id', '')),
                    str(data.get('name', '')),
                    str(data.get('start_time', '')),
                    str(data.get('end_time', '')),
                )
            )
    records.sort(key=lambda item: (item[2], item[0]))
    for record in records:
        digest.update('|'.join(record).encode('utf-8'))
    return digest.hexdigest()


BASE = Path(__file__).resolve().parents[2]
DATA = BASE / "data" / "demo" / "threads"
RUNS = BASE / "runs"
RUNS.mkdir(exist_ok=True, parents=True)

app = FastAPI(title="OverhearOps")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TRACER = init_otel("overhearops")
GRAPH = build_graph(db_url=os.getenv("OVERHEAROPS_DB", "overhearops.db"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def iter_ndjson(thread_id: str) -> AsyncGenerator[dict[str, Any], None]:
    path = DATA / f"{thread_id}.ndjson"
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


@app.websocket("/stream/{thread_id}")
async def stream(ws: WebSocket, thread_id: str) -> None:
    await ws.accept()
    try:
        async for message in iter_ndjson(thread_id):
            await ws.send_json(message)
            await asyncio.sleep(0.35)
    except WebSocketDisconnect:
        return


@app.post("/run/{thread_id}")
async def run(thread_id: str) -> dict[str, Any]:
    last: dict[str, Any] | None = None
    async for message in iter_ndjson(thread_id):
        last = message
    run_id = f"demo-{thread_id}-{int(time.time())}"
    config = {"configurable": {"thread_id": run_id}}
    run_dir = RUNS / run_id
    run_dir.mkdir(exist_ok=True, parents=True)
    previous_run_id = os.getenv("OVERHEAROPS_RUN_ID")
    os.environ["OVERHEAROPS_RUN_ID"] = run_id
    try:
        state: dict[str, Any] = GRAPH.invoke(
            {"msg": last or {}, "thread_id": run_id}, config=config
        )
    finally:
        if previous_run_id is not None:
            os.environ["OVERHEAROPS_RUN_ID"] = previous_run_id
        else:
            os.environ.pop("OVERHEAROPS_RUN_ID", None)

    provider = trace.get_tracer_provider()
    flush = getattr(provider, "force_flush", None)
    if callable(flush):
        flush()
    graphs = build_graphs(run_id)
    replay_hash = _compute_replay_hash(run_id)

    artefacts = {
        "verdict": state.get("verdict", {}),
        "artefacts": state.get("artefacts", {}),
        "plans": state.get("plans", []),
        "replay_hash": replay_hash,
        "graphs": graphs,
    }
    with (run_dir / "artefacts.json").open("wb") as fh:
        fh.write(orjson.dumps(artefacts))
    with (run_dir / "graphs.json").open("wb") as fh:
        fh.write(orjson.dumps(graphs))
    (run_dir / "hash.txt").write_text(replay_hash, encoding="utf-8")

    return {"run_id": run_id, "verdict": artefacts["verdict"]}


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    path = RUNS / run_id / "artefacts.json"
    if not path.exists():
        return {"error": "not found"}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@app.get("/runs/{run_id}/graphs.json")
async def get_graphs(run_id: str) -> dict[str, Any]:
    return build_graphs(run_id)
