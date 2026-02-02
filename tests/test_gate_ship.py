import pytest

from packages.agentkit.uncertainty import approve_if_confident


def test_gate_adds_action_and_certainty():
    verdict = {"winner_plan_id": "plan-a", "winner_votes": 2}
    gated = approve_if_confident(verdict)
    assert gated["action"] == "approve"
    assert gated["certainty"] == pytest.approx(2 / 3)
