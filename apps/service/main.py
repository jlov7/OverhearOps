from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

import orjson
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from packages.agentkit.graph import build_graph
from packages.obs.action_graph import simple_linear_graph
from packages.obs.otel import init_otel

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
    state: dict[str, Any] = GRAPH.invoke({"msg": last or {}}, config=config)

    artefacts = {
        "verdict": state.get("verdict", {}),
        "artefacts": state.get("artefacts", {}),
        "action_graph": simple_linear_graph(
            ["overhear", "team", "plan", "exec", "judge", "gate", "ship"]
        ),
    }
    run_dir = RUNS / run_id
    run_dir.mkdir(exist_ok=True, parents=True)
    with (run_dir / "artefacts.json").open("wb") as fh:
        fh.write(orjson.dumps(artefacts))

    return {"run_id": run_id, "verdict": artefacts["verdict"]}


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    path = RUNS / run_id / "artefacts.json"
    if not path.exists():
        return {"error": "not found"}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
