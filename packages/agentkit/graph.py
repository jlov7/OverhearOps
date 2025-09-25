from __future__ import annotations

import atexit
import os
from typing import Any, TypedDict, cast

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from packages.agentkit.agentinit import compose_team
from packages.agentkit.executor import try_patch_or_issue
from packages.agentkit.judge import multi_agent_judge
from packages.agentkit.overhear import detect_intents_from_stream
from packages.agentkit.planner import fork_plans
from packages.agentkit.uncertainty import approve_if_confident


class State(TypedDict, total=False):
    msg: dict[str, Any]
    intents: list[str]
    plans: list[dict[str, Any]]
    branches: list[dict[str, Any]]
    verdict: dict[str, Any]
    artefacts: dict[str, Any]
    risk: dict[str, Any]
    team: list[dict[str, Any]]


def node_overhear(state: State) -> State:
    body = state.get("msg", {}).get("body", {})
    content = body.get("content", "")
    intents, confidence = detect_intents_from_stream(content)
    threshold = float(os.getenv("OVERHEAROPS_INTENT_THRESHOLD", "0.6"))
    return {**state, "intents": intents} if confidence >= threshold else {**state, "intents": []}


def node_team(state: State) -> State:
    return {**state, "team": compose_team(state.get("intents", []))}


def node_plan(state: State) -> State:
    plans = fork_plans(state.get("msg", {}))
    return {**state, "plans": plans, "branches": [{"plan": plan} for plan in plans]}


def node_exec(state: State) -> State:
    plan = state.get("plan")
    if plan is None and state.get("branches"):
        branch_plan = state["branches"][0].get("plan")
        plan = branch_plan if isinstance(branch_plan, dict) else {}
    if not isinstance(plan, dict):
        plan = {}
    return {**state, "artefacts": try_patch_or_issue(plan)}


def node_judge(state: State) -> State:
    plans = state.get("plans", [])
    return {**state, "verdict": multi_agent_judge([{"plan": plan} for plan in plans])}


def node_gate(state: State) -> State:
    return {**state, "verdict": approve_if_confident(state.get("verdict", {}))}


def node_ship(state: State) -> State:
    return state


def build_graph(db_url: str = "overhearops.db"):
    graph = StateGraph(State)
    graph.add_node("overhear", node_overhear)
    graph.add_node("team", node_team)
    graph.add_node("plan", node_plan)
    graph.add_node("exec", node_exec)
    graph.add_node("judge", node_judge)
    graph.add_node("gate", node_gate)
    graph.add_node("ship", node_ship)

    graph.add_edge(START, "overhear")
    graph.add_edge("overhear", "team")
    graph.add_edge("team", "plan")
    graph.add_conditional_edges(
        "plan",
        lambda state: ["exec"] * len(state.get("branches", [])),
        ["exec"],
    )
    graph.add_edge("exec", "judge")
    graph.add_edge("judge", "gate")
    graph.add_edge("gate", "ship")
    graph.add_edge("ship", END)

    saver_cm = SqliteSaver.from_conn_string(db_url)
    checkpointer = cast(SqliteSaver, saver_cm.__enter__())
    atexit.register(saver_cm.__exit__, None, None, None)
    return graph.compile(checkpointer=checkpointer)
