"""Planner node synthesising candidate remediation branches."""

from __future__ import annotations

import itertools
import os
from typing import Any

PLAN_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "ci_flake": [
        {
            "id": "plan-quarantine",
            "title": "Quarantine flaky test to unblock release",
            "hypothesis": (
                "Removing the failing test restores signal "
                "whilst investigation continues"
            ),
            "steps": [
                "Mark integration/test_artifacts as xfail for release branch",
                "Add monitoring hook for retries",
                "Document exemption with expiry date",
            ],
            "blast_radius": "Low",
            "confidence": 0.62,
        },
        {
            "id": "plan-timeout",
            "title": "Extend fixture timeout and capture diagnostics",
            "hypothesis": (
                "Fixture start occasionally exceeds 600s; more time "
                "+ profiling yields evidence"
            ),
            "steps": [
                "Increase api_server fixture timeout to 900s",
                "Enable CPU profiling via py-spy",
                "Archive flamegraphs as pipeline artefacts",
            ],
            "blast_radius": "Medium",
            "confidence": 0.55,
        },
        {
            "id": "plan-renderer-patch",
            "title": "Patch PDF renderer worker leak",
            "hypothesis": "Zombie workers from new renderer stall teardown and starve tests",
            "steps": [
                "Audit worker lifecycle for orphaned processes",
                "Add guard to terminate idle workers",
                "Roll out behind feature flag",
            ],
            "blast_radius": "Medium",
            "confidence": 0.48,
        },
    ]
}


_fallback_counter = itertools.count(1)


def _branch_cap() -> int:
    try:
        return max(1, int(os.getenv("OVERHEAROPS_BRANCH_WIDTH", "3")))
    except ValueError:
        return 3


def _intent_from_message(message: dict[str, Any]) -> str:
    content = str(message.get("body", {}).get("content", "")).lower()
    if any(keyword in content for keyword in ["cve", "exploit", "rotation"]):
        return "security"
    if any(keyword in content for keyword in ["policy", "regulation", "privacy"]):
        return "policy_change"
    return "ci_flake"


def fork_plans(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a list of plan candidates constrained by branch width."""

    intent = _intent_from_message(message)
    candidates: list[dict[str, Any]] = list(PLAN_LIBRARY.get(intent, PLAN_LIBRARY["ci_flake"]))
    while len(candidates) < 3:
        idx = next(_fallback_counter)
        candidates.append(
            {
                "id": f"plan-fallback-{idx}",
                "title": "Investigate incident",
                "hypothesis": "Fallback plan generated to maintain branch diversity",
                "steps": [
                    "Collect additional telemetry",
                    "Confirm reproduction steps",
                    "Escalate to on-call owner",
                ],
                "blast_radius": "Unknown",
                "confidence": 0.4,
            }
        )
    return candidates[: _branch_cap()]


__all__ = ["fork_plans"]
