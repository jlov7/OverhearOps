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
    agent_roles: set[str] = set()
    tool_names: set[str] = set()
    memory_refs: set[str] = set()

    with span_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            data = json.loads(line)
            span_id = _as_hex(data.get("span_id"))
            parent = data.get("parent_id")
            attributes = data.get("attributes", {}) or {}
            label = data.get("name", "span")
            action_nodes.append(
                {
                    "id": span_id,
                    "label": label,
                    "trace_id": _as_hex(data.get("trace_id")),
                    "t0": data.get("start_time"),
                    "t1": data.get("end_time"),
                    "attrs": attributes,
                }
            )
            if parent:
                action_edges.append({"source": _as_hex(parent), "target": span_id})
            agent_role = attributes.get("agent.role")
            if isinstance(agent_role, str):
                agent_roles.add(agent_role)
            tool = attributes.get("tool.name")
            if isinstance(tool, str):
                tool_names.add(tool)
            memory = attributes.get("memory.ref")
            if isinstance(memory, str):
                memory_refs.add(memory)

    if not action_edges and len(action_nodes) > 1:
        ordered = sorted(action_nodes, key=lambda node: node.get("t0") or 0)
        for first, second in zip(ordered, ordered[1:], strict=False):
            action_edges.append({"source": first["id"], "target": second["id"]})

    component_nodes: list[dict[str, Any]] = []
    if agent_roles:
        component_nodes.append(
            {"id": "agents", "label": "Agents", "items": sorted(agent_roles)}
        )
    if tool_names:
        component_nodes.append(
            {"id": "tools", "label": "Tools", "items": sorted(tool_names)}
        )
    if memory_refs:
        component_nodes.append(
            {"id": "memory", "label": "Memory", "items": sorted(memory_refs)}
        )

    return {
        "action_graph": {"nodes": action_nodes, "edges": action_edges},
        "component_graph": {"nodes": component_nodes, "edges": []},
    }


__all__ = ["build_graphs"]
