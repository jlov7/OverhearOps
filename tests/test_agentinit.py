from packages.agentkit.agentinit import compose_team


def test_compose_team_roles():
    team = compose_team(["ci_flake"])
    roles = {member["role"] for member in team}
    assert roles == {"Coordinator", "Fixer", "Critic", "RiskGuard"}
    fixer = next(member for member in team if member["role"] == "Fixer")
    assert "asyncio" in fixer["skills"]
