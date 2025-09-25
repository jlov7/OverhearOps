from packages.agentkit.judge import multi_agent_judge
from packages.agentkit.uncertainty import approve_if_confident


def test_multi_agent_judge_returns_winner():
    branches = [
        {"plan": {"id": "a", "confidence": 0.7, "blast_radius": "Low", "steps": ["step"]}},
        {"plan": {"id": "b", "confidence": 0.5, "blast_radius": "Medium", "steps": ["step"]}},
    ]
    verdict = multi_agent_judge(branches)
    assert verdict["winner"]["plan"]["id"] == "a"
    assert verdict["votes"]


def test_approve_if_confident_sets_action():
    verdict = {"winner": {"plan": {"id": "a"}, "votes": 2}}
    updated = approve_if_confident(verdict)
    assert updated["action"] in {"approve", "abstain"}
    assert 0.0 <= updated["certainty"] <= 1.0
