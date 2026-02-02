from __future__ import annotations

import atexit
import json
import os
from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any, TypedDict, cast

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from opentelemetry import trace
from opentelemetry.trace import Span

from packages.agentkit.agentinit import compose_team
from packages.agentkit.executor import try_patch_or_issue
from packages.agentkit.judge import multi_agent_judge
from packages.agentkit.overhear import detect_intents_from_stream
from packages.agentkit.planner import fork_plans
from packages.agentkit.uncertainty import approve_if_confident

tracer = trace.get_tracer("overhearops.graph")
# Preserve span lineage for action graphs; mirrors LangGraph durable execution guidance.
current_span_var: ContextVar[Span | None] = ContextVar("overhearops_current_span", default=None)


class State(TypedDict, total=False):
    msg: dict[str, Any]
    intents: list[str]
    plans: list[dict[str, Any]]
    branches: list[dict[str, Any]]
    verdict: dict[str, Any]
    artefacts: dict[str, Any]
    risk: dict[str, Any]
    team: list[dict[str, Any]]


StateCallable = Callable[[State], State]


def _token_proxy(payload: Any) -> int:
    try:
        text = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    except TypeError:
        text = str(payload)
    return max(0, len(text) // 4)


def _branch_identifier(state: State) -> str | None:
    plan = state.get("plan")
    if isinstance(plan, dict) and plan.get("id"):
        return str(plan["id"])
    branches = state.get("branches")
    if isinstance(branches, list):
        for candidate in branches:
            if not isinstance(candidate, dict):
                continue
            branch_plan = candidate.get("plan")
            if isinstance(branch_plan, dict) and branch_plan.get("id"):
                return str(branch_plan["id"])
    return None


def spanify(name: str) -> Callable[[StateCallable], StateCallable]:
    def decorator(fn: StateCallable) -> StateCallable:
        @wraps(fn)
        def wrapped(state: State) -> State:
            approx_in = _token_proxy(state)
            parent = current_span_var.get()
            context = trace.set_span_in_context(parent) if parent else None
            token = None
            with tracer.start_as_current_span(name, context=context) as span:
                token = current_span_var.set(span)
                span.set_attribute("agent.role", name)
                thread_id = state.get("thread_id")
                if thread_id:
                    span.set_attribute("overhearops.thread_id", str(thread_id))
                branch_id = _branch_identifier(state)
                if branch_id:
                    span.set_attribute("branch.id", branch_id)
                span.set_attribute("token.approx_in", approx_in)
                try:
                    result = fn(state)
                except Exception:
                    span.set_attribute("token.approx_out", 0)
                    raise
                else:
                    span.set_attribute("token.approx_out", _token_proxy(result))
                    return result
                finally:
                    if token is not None:
                        current_span_var.reset(token)

        return wrapped

    return decorator

@spanify("overhear")
def node_overhear(state: State) -> State:
    body = state.get("msg", {}).get("body", {})
    content = body.get("content", "")
    intents, confidence = detect_intents_from_stream(content)
    threshold = float(os.getenv("OVERHEAROPS_INTENT_THRESHOLD", "0.6"))
    return {**state, "intents": intents} if confidence >= threshold else {**state, "intents": []}


@spanify("team")
def node_team(state: State) -> State:
    return {**state, "team": compose_team(state.get("intents", []))}


@spanify("plan")
def node_plan(state: State) -> State:
    thread_id = str(state.get("thread_id", "ci_flake"))
    plans = fork_plans(state.get("msg", {}), thread_id=thread_id)
    return {**state, "plans": plans, "branches": [{"plan": plan} for plan in plans]}


@spanify("exec")
def node_exec(state: State) -> State:
    plan = state.get("plan")
    if plan is None and state.get("branches"):
        branch_plan = state["branches"][0].get("plan")
        plan = branch_plan if isinstance(branch_plan, dict) else {}
    if not isinstance(plan, dict):
        plan = {}
    return {**state, "artefacts": try_patch_or_issue(plan)}


@spanify("judge")
def node_judge(state: State) -> State:
    thread_id = str(state.get("thread_id", "ci_flake"))
    plans = state.get("plans", [])
    return {
        **state,
        "verdict": multi_agent_judge([{"plan": plan} for plan in plans], thread_id=thread_id),
    }


@spanify("gate")
def node_gate(state: State) -> State:
    return {**state, "verdict": approve_if_confident(state.get("verdict", {}))}


@spanify("ship")
def node_ship(state: State) -> State:
    return state


def build_graph(db_url: str = "overhearops.db"):
    graph = StateGraph(State)
    graph.add_node("overhear", node_overhear, input_schema=State)  # type: ignore[arg-type, call-overload]
    graph.add_node("team", node_team, input_schema=State)  # type: ignore[arg-type, call-overload]
    graph.add_node("plan", node_plan, input_schema=State)  # type: ignore[arg-type, call-overload]
    graph.add_node("exec", node_exec, input_schema=State)  # type: ignore[arg-type, call-overload]
    graph.add_node("judge", node_judge, input_schema=State)  # type: ignore[arg-type, call-overload]
    graph.add_node("gate", node_gate, input_schema=State)  # type: ignore[arg-type, call-overload]
    graph.add_node("ship", node_ship, input_schema=State)  # type: ignore[arg-type, call-overload]

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
