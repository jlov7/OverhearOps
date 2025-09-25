"""Keyword heuristics for overhearing Teams threads.

Grounded in the "Overhearing LLM Agents" survey (see `docs/RESEARCH.yml`), we
score lightweight lexical signals so the demo works offline yet stays
interpretable. The function returns a ranked list of candidate intents plus a
confidence proxy for gating.
"""

from __future__ import annotations

import math
import re

LABEL_KEYWORDS: dict[str, dict[str, float]] = {
    "ci_flake": {
        "timeout": 1.0,
        "pytest": 0.8,
        "pipeline": 0.6,
        "rerun": 0.6,
        "flake": 0.9,
        "fixture": 0.5,
    },
    "security": {
        "cve": 1.0,
        "exploit": 0.9,
        "patch": 0.6,
        "rotation": 0.4,
        "vuln": 0.9,
    },
    "policy_change": {
        "policy": 0.8,
        "privacy": 0.7,
        "legal": 0.6,
        "compliance": 0.9,
    },
}


def _tokenise(content: str) -> list[str]:
    return re.findall(r"[a-z0-9_#]+", content.lower())


def _score(tokens: list[str], weights: dict[str, float]) -> tuple[float, list[str]]:
    score = 0.0
    evidence: list[str] = []
    for token in tokens:
        weight = weights.get(token)
        if not weight:
            continue
        score += weight
        evidence.append(token)
    return score, evidence


def detect_intents_from_stream(content: str) -> tuple[list[str], float]:
    """Return (intents, confidence) extracted from a chat message body."""

    tokens = _tokenise(content)
    if not tokens:
        return [], 0.0

    raw_scores: dict[str, float] = {}
    evidences: dict[str, list[str]] = {}
    for label, weights in LABEL_KEYWORDS.items():
        raw, evidence = _score(tokens, weights)
        raw_scores[label] = raw
        evidences[label] = evidence

    if not any(raw_scores.values()):
        return [], 0.0

    max_score = max(raw_scores.values())
    exp_scores = {label: math.exp(score - max_score) for label, score in raw_scores.items()}
    total = sum(exp_scores.values()) or 1.0
    probabilities = {label: value / total for label, value in exp_scores.items()}

    ranked = sorted(
        ((label, prob) for label, prob in probabilities.items() if raw_scores[label] > 0.0),
        key=lambda item: item[1],
        reverse=True,
    )
    intents = [label for label, _ in ranked]
    top_conf = ranked[0][1] if ranked else 0.0
    return intents, top_conf


__all__ = ["detect_intents_from_stream"]
