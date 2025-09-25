"""AgentInit-inspired team formation.

Inspired by AgentInit (see `docs/RESEARCH.yml`), we build a micro-team with
complementary personas for the detected incident intents. The implementation
keeps heuristics deterministic for demo purposes while documenting future
LLM-backed expansion.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Persona:
    role: str
    persona: str
    focus: str
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


ROLE_LIBRARY: dict[str, Persona] = {
    "Coordinator": Persona(
        role="Coordinator",
        persona="Incident Strategist",
        focus="Frames hypotheses and sequencing",
        skills=["triage", "timeline"],
    ),
    "Fixer": Persona(
        role="Fixer",
        persona="Senior Reliability Engineer",
        focus="Owns code-level mitigation",
        skills=["python", "profiling"],
    ),
    "Critic": Persona(
        role="Critic",
        persona="QA Skeptic",
        focus="Surfaces blast radius and edge cases",
        skills=["test review", "risk mapping"],
    ),
    "RiskGuard": Persona(
        role="RiskGuard",
        persona="Compliance Analyst",
        focus="Checks policy and governance constraints",
        skills=["policy", "audit"],
    ),
}

INTENT_TO_SPECIALISMS: dict[str, dict[str, list[str]]] = {
    "ci_flake": {
        "Coordinator": ["pytest triage"],
        "Fixer": ["asyncio", "perf"],
        "Critic": ["determinism"],
        "RiskGuard": ["release policy"],
    },
    "security": {
        "Coordinator": ["incident comms"],
        "Fixer": ["patch", "rotations"],
        "Critic": ["threat model"],
        "RiskGuard": ["exposure classification"],
    },
    "policy_change": {
        "Coordinator": ["stakeholder map"],
        "Fixer": ["doc update"],
        "Critic": ["customer impact"],
        "RiskGuard": ["regulatory"],
    },
}

SPECIALISM_TOOLS = {
    "pytest triage": ["pytest", "coverage"],
    "asyncio": ["py-spy"],
    "perf": ["scalene"],
    "determinism": ["flake-finder"],
    "release policy": ["runbook"],
    "patch": ["git"],
    "rotations": ["vault-cli"],
    "threat model": ["threatspec"],
    "incident comms": ["statuspage"],
    "doc update": ["confluence"],
}


def _intent_key(intents: list[str]) -> str:
    return intents[0] if intents else "ci_flake"


def compose_team(intents: list[str]) -> list[dict[str, object]]:
    """Return serialisable team blueprint for downstream nodes."""

    intent = _intent_key(intents)
    specialisms = INTENT_TO_SPECIALISMS.get(intent, INTENT_TO_SPECIALISMS["ci_flake"])
    team: list[dict[str, object]] = []
    for role, persona in ROLE_LIBRARY.items():
        skills = sorted(set(persona.skills + specialisms.get(role, [])))
        tools = sorted({tool for skill in skills for tool in SPECIALISM_TOOLS.get(skill, [])})
        team.append(
            {
                "role": persona.role,
                "persona": persona.persona,
                "focus": persona.focus,
                "skills": skills,
                "tools": tools,
            }
        )
    return team


__all__ = ["compose_team"]
