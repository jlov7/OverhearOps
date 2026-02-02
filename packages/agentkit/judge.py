"""Multi-agent heuristic judge for plan selection."""
from __future__ import annotations

import os
from collections import Counter
from typing import Any

from packages.agentkit.provider import OfflineProvider


def _score(plan: dict[str, Any]) -> float:
    confidence = float(plan.get("confidence", 0.0))
    blast = str(plan.get("blast_radius", "")).lower()
    penalty = 0.2 if "high" in blast else 0.1 if "medium" in blast else 0.0
    steps = plan.get("steps", [])
    step_count = len(steps) if isinstance(steps, list) else 0
    return confidence - penalty + 0.02 * step_count


def _provider() -> OfflineProvider | None:
    mode = os.getenv("OVERHEAROPS_LLM_MODE", "offline")
    if mode == "offline":
        base_dir = os.getenv("OVERHEAROPS_LLM_BASE_DIR", "data/demo/llm")
        return OfflineProvider(base_dir)
    return None


def _winner_plan(branches: list[dict[str, Any]], winner_id: str | None) -> dict[str, Any]:
    if not winner_id:
        return {}
    for entry in branches:
        plan = entry.get("plan", {})
        if isinstance(plan, dict) and plan.get("id") == winner_id:
            return plan
    return {}


def multi_agent_judge(branches: list[dict[str, Any]], thread_id: str = "ci_flake") -> dict[str, Any]:
    """Return judge verdict capturing votes and rationale."""

    provider = _provider()
    if provider:
        data = provider.generate_json("judge", thread_id=thread_id)
        winner_id = data.get("winner_plan_id") if isinstance(data, dict) else None
        votes = data.get("votes", []) if isinstance(data, dict) else []
        winner_votes = len([vote for vote in votes if vote.get("plan_id") == winner_id])
        winner_plan = _winner_plan(branches, winner_id)
        if not winner_plan and branches:
            provider = None
        else:
            uncertainty = "medium" if winner_votes == 2 else "low"
            return {
                "winner_plan_id": winner_id,
                "winner": {"plan": winner_plan, "votes": winner_votes},
                "rationale": data.get("rationale", "Offline verdict") if isinstance(data, dict) else "Offline verdict",
                "uncertainty": uncertainty,
                "votes": votes,
            }

    if not branches:
        return {"winner": {"plan": {}}, "rationale": "No branches", "uncertainty": "high"}

    votes: list[dict[str, Any]] = []
    tally: Counter[str] = Counter()
    personas = ["Coordinator", "Critic", "RiskGuard"]

    for entry in branches:
        plan = entry.get("plan", {})
        if not isinstance(plan, dict):
            continue
        score = _score(plan)
        blast = str(plan.get("blast_radius", "")).lower()
        for persona in personas:
            persona_score = score
            if persona == "Critic" and "medium" in blast:
                persona_score -= 0.05
            if persona == "RiskGuard" and "low" in blast:
                persona_score += 0.1
            votes.append({"persona": persona, "plan_id": plan.get("id"), "score": persona_score})

    persona_choice: dict[str, dict[str, Any]] = {}
    for vote in votes:
        persona = vote["persona"]
        current = persona_choice.get(persona)
        if current is None or vote["score"] > current["score"]:
            persona_choice[persona] = vote

    for choice in persona_choice.values():
        tally[choice["plan_id"]] += 1

    winner_id, winner_votes = tally.most_common(1)[0]
    winner_plan = next(
        entry["plan"]
        for entry in branches
        if isinstance(entry.get("plan"), dict)
        and entry["plan"].get("id") == winner_id
    )
    if not isinstance(winner_plan, dict):
        winner_plan = {}
    rationale = f"Majority vote ({winner_votes}/{len(personas)}) favours {winner_plan.get('title')}"

    return {
        "winner": {"plan": winner_plan, "votes": winner_votes},
        "rationale": rationale,
        "uncertainty": "medium" if winner_votes == 2 else "low",
        "votes": votes,
    }


__all__ = ["multi_agent_judge"]
