from packages.agentkit.executor import exec_all_plans


def test_exec_all_plans_returns_per_plan_artefacts():
    plans = [
        {"id": "plan-a", "title": "A", "steps": ["x"], "confidence": 0.6},
        {"id": "plan-b", "title": "B", "steps": ["y"], "confidence": 0.5},
    ]
    artefacts = exec_all_plans(plans)
    assert set(artefacts.keys()) == {"plan-a", "plan-b"}
