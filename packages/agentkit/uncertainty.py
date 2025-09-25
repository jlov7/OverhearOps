"""Uncertainty gate that approves only when confidence clears a threshold."""

from __future__ import annotations

from typing import Any

TOTAL_VOTERS = 3


def approve_if_confident(verdict: dict[str, Any]) -> dict[str, Any]:
    """Add action + certainty fields based on judge vote count."""

    winner = verdict.get("winner", {})
    votes = int(winner.get("votes", 0))
    certainty = votes / TOTAL_VOTERS if TOTAL_VOTERS else 0.0
    action = "approve" if certainty >= 2 / TOTAL_VOTERS else "abstain"
    return {**verdict, "action": action, "certainty": certainty}


__all__ = ["approve_if_confident"]
