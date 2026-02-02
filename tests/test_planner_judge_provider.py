from packages.agentkit.judge import multi_agent_judge
from packages.agentkit.planner import fork_plans


def test_planner_uses_offline_provider(monkeypatch):
    monkeypatch.setenv("OVERHEAROPS_LLM_MODE", "offline")
    monkeypatch.setenv("OVERHEAROPS_LLM_BASE_DIR", "data/demo/llm")
    plans = fork_plans({"body": {"content": "ci flake"}}, thread_id="ci_flake")
    assert plans[0]["id"] == "plan-quarantine"


def test_judge_uses_offline_provider(monkeypatch):
    monkeypatch.setenv("OVERHEAROPS_LLM_MODE", "offline")
    monkeypatch.setenv("OVERHEAROPS_LLM_BASE_DIR", "data/demo/llm")
    verdict = multi_agent_judge([{"plan": {"id": "plan-quarantine"}}], thread_id="ci_flake")
    assert verdict["winner_plan_id"] == "plan-quarantine"
