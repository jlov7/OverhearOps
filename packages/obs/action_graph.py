"""Derive action/component graphs from captured OTEL spans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _base_path(run_id: str) -> Path:
    return Path(__file__).resolve().parents[2] / "runs" / run_id / "spans.jsonl"


def _as_hex(value: Any) -> str:
    try:
        return f"{int(value):x}"
    except (TypeError, ValueError):
        return str(value)


def build_graphs(run_id: str) -> dict[str, Any]:
    span_path = _base_path(run_id)
    if not span_path.exists():
        empty: dict[str, list[Any]] = {"nodes": [], "edges": []}
        return {"action_graph": empty, "component_graph": empty}

    action_nodes: list[dict[str, Any]] = []
    action_edges: list[dict[str, Any]] = []

    with span_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            data = json.loads(line)
            span_id = _as_hex(data.get("span_id"))
            parent = data.get("parent_id")
            parent_id = _as_hex(parent) if parent else None
            attributes = data.get("attributes", {}) or {}

            action_nodes.append(
                {
                    "id": span_id,
                    "label": data.get("name", "span"),
                    "trace_id": _as_hex(data.get("trace_id")),
                    "t0": data.get("start_time"),
                    "t1": data.get("end_time"),
                    "attrs": attributes,
                }
            )
            if parent_id:
                action_edges.append({"source": parent_id, "target": span_id})

    if len(action_nodes) > 1:
        ordered = sorted(action_nodes, key=lambda node: node.get("t0") or 0)
        existing = {(edge["source"], edge["target"]) for edge in action_edges}
        for first, second in zip(ordered, ordered[1:], strict=False):
            pair = (first["id"], second["id"])
            if pair not in existing:
                action_edges.append({"source": first["id"], "target": second["id"]})

    return {
        "action_graph": {"nodes": action_nodes, "edges": action_edges},
        "component_graph": {"nodes": [], "edges": []},
    }


__all__ = ["build_graphs"]
