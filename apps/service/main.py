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
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace

from apps.service.adapters.teams_demo import (
    iter_messages as demo_iter_messages,
    list_threads as demo_list_threads,
)
from apps.service.adapters.teams_graph import TeamsGraphAdapter
from packages.agentkit.graph import build_graph
from packages.obs.action_graph import build_graphs
from packages.obs.otel import init_otel
from packages.obs.runtime import set_run_context


def _spans_path(run_id: str) -> Path:
    return RUNS / run_id / 'spans.jsonl'


def _compute_replay_hash(run_id: str) -> str:
    digest = hashlib.sha256()
    span_file = _spans_path(run_id)
    if not span_file.exists():
        digest.update(run_id.encode('utf-8'))
        return digest.hexdigest()
    records: list[dict[str, Any]] = []
    with span_file.open('r', encoding='utf-8') as handle:
        for line in handle:
            data = json.loads(line)
            attributes = data.get('attributes')
            if not isinstance(attributes, dict):
                attributes = {}
            stable_attrs = {key: attributes[key] for key in sorted(attributes)}
            records.append(
                {
                    "name": str(data.get('name', '')),
                    "attributes": stable_attrs,
                }
            )
    records.sort(key=lambda item: (item["name"], json.dumps(item["attributes"], sort_keys=True, default=str)))
    for record in records:
        digest.update(json.dumps(record, sort_keys=True, default=str).encode('utf-8'))
    return digest.hexdigest()


BASE = Path(__file__).resolve().parents[2]
RUNS = BASE / "runs"
RUNS.mkdir(exist_ok=True, parents=True)

ADAPTER_MODE = os.getenv("ADAPTER", "demo").lower()
_GRAPH_ADAPTER: TeamsGraphAdapter | None = None

PLAYGROUND_PLAN_CARD: dict[str, Any] = {
    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
    "type": "AdaptiveCard",
    "version": "1.5",
    "body": [
        {"type": "TextBlock", "text": "OverhearOps Plan B", "weight": "Bolder", "size": "Medium"},
        {"type": "TextBlock", "text": "Increase timeout to 120s on Windows", "wrap": True},
        {
            "type": "FactSet",
            "facts": [
                {"title": "Confidence", "value": "0.74"},
                {"title": "Estimated cost", "value": "~3.2k tokens"},
                {"title": "Blast radius", "value": "Low"},
            ],
        },
    ],
    "actions": [
        {"type": "Action.Submit", "title": "Ship (dry-run)", "data": {"action": "ship_plan_b"}},
        {"type": "Action.Submit", "title": "Show Diff", "data": {"action": "show_diff"}},
    ],
}


def _graph_adapter() -> TeamsGraphAdapter:
    global _GRAPH_ADAPTER
    if _GRAPH_ADAPTER is None:
        try:
            _GRAPH_ADAPTER = TeamsGraphAdapter()
        except RuntimeError as exc:  # pragma: no cover - exercised via HTTPException
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _GRAPH_ADAPTER


def _resolve_graph_targets(thread_id: str) -> tuple[str, str]:
    if ":" in thread_id:
        team_id, channel_id = thread_id.split(":", 1)
        return team_id, channel_id
    return thread_id, thread_id


def _load_thread_messages(thread_id: str) -> list[dict[str, Any]]:
    if ADAPTER_MODE in {"demo", "playground"}:
        try:
            messages = list(demo_iter_messages(thread_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not messages:
            raise HTTPException(
                status_code=404,
                detail=f"No messages recorded for thread {thread_id}.",
            )
        return messages
    if ADAPTER_MODE == "graph":
        adapter = _graph_adapter()
        team_id, channel_id = _resolve_graph_targets(thread_id)
        messages = list(adapter.list_messages(team_id, channel_id))
        if not messages:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Teams Graph adapter configured but returned no messages; provide valid IDs "
                    "or extend the stub."
                ),
            )
        return messages
    raise HTTPException(status_code=400, detail=f"Unknown adapter mode: {ADAPTER_MODE}")


async def iter_messages(thread_id: str) -> AsyncGenerator[dict[str, Any], None]:
    if ADAPTER_MODE == "graph":
        adapter = _graph_adapter()
        for message in adapter.stream_thread(thread_id):
            yield message
        return
    messages = _load_thread_messages(thread_id)
    for message in messages:
        yield message


app = FastAPI(title="OverhearOps")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

THREAD_EVENTS: dict[str, list[dict[str, Any]]] = {}

TRACER = init_otel("overhearops")
GRAPH = build_graph(db_url=os.getenv("OVERHEAROPS_DB", "overhearops.db"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/playground/card/plan")
def playground_plan_card() -> dict[str, Any]:
    if ADAPTER_MODE != "playground":
        raise HTTPException(
            status_code=404,
            detail="Playground mode disabled; set ADAPTER=playground to expose the sample card.",
        )
    return PLAYGROUND_PLAN_CARD


@app.get("/threads")
def list_threads() -> dict[str, int]:
    if ADAPTER_MODE in {"demo", "playground"}:
        return demo_list_threads()
    return {}


@app.get("/threads/{thread_id}")
def get_thread(thread_id: str) -> list[dict[str, Any]]:
    return _load_thread_messages(thread_id)


@app.post("/threads/{thread_id}/events")
def ingest_event(thread_id: str, payload: dict[str, Any]) -> dict[str, str]:
    THREAD_EVENTS.setdefault(thread_id, []).append(payload)
    return {"status": "ok"}


@app.websocket("/stream/{thread_id}")
async def stream(ws: WebSocket, thread_id: str) -> None:
    await ws.accept()
    try:
        async for message in iter_messages(thread_id):
            await ws.send_json(message)
            await asyncio.sleep(0.35)
    except HTTPException as exc:
        await ws.send_json({"error": exc.detail})
        await ws.close()
    except WebSocketDisconnect:
        return


@app.post("/run/{thread_id}")
async def run(thread_id: str) -> dict[str, Any]:
    messages = _load_thread_messages(thread_id)
    last = messages[-1] if messages else {}
    run_id = f"{ADAPTER_MODE}-{thread_id}-{int(time.time())}"
    config = {"configurable": {"thread_id": run_id}}
    run_dir = RUNS / run_id
    run_dir.mkdir(exist_ok=True, parents=True)
    previous_run_id = os.getenv("OVERHEAROPS_RUN_ID")
    os.environ["OVERHEAROPS_RUN_ID"] = run_id
    set_run_context(run_id=run_id, mode=os.getenv("OVERHEAROPS_LLM_MODE"), provider=os.getenv("OVERHEAROPS_LLM_PROVIDER"))
    try:
        state: dict[str, Any] = GRAPH.invoke(
            {"msg": last or {}, "thread_id": thread_id}, config=config
        )
    finally:
        set_run_context(run_id=None, mode=None, provider=None)
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

    verdict = state.get("verdict", {})
    artefacts = {
        "run_id": run_id,
        "thread_id": thread_id,
        "mode": os.getenv("OVERHEAROPS_LLM_MODE", "offline"),
        "provider": os.getenv("OVERHEAROPS_LLM_PROVIDER", "offline"),
        "verdict": verdict,
        "gate": {
            "action": verdict.get("action"),
            "certainty": verdict.get("certainty"),
        },
        "artefacts": state.get("artefacts", {}),
        "artefacts_by_plan": state.get("artefacts_by_plan", {}),
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
