from packages.agentkit.agentinit import compose_team
from packages.agentkit.executor import try_patch_or_issue
from packages.agentkit.planner import fork_plans


def test_fork_plans_and_executor():
    plans = fork_plans({"body": {"content": "CI failure"}})
    assert len(plans) >= 1
    compose_team(["ci_flake"])
    artefacts = try_patch_or_issue(plans[0])
    assert artefacts["plan"]["id"] == plans[0]["id"]
    assert artefacts["pr_diff"].startswith("diff --git")
