from packages.obs.defence import ATTACK_CASES, guard_tool_call, run_defence


def test_attack_suite_blocked():
    for case in ATTACK_CASES:
        decision = run_defence(case["prompt"])
        assert not decision.allowed, f"Prompt escaped guard: {case}"
        assert case["category"] in decision.categories


def test_guard_blocks_dangerous_tools():
    decision = guard_tool_call({"name": "exec", "args": "rm -rf /"})
    assert not decision.allowed
    assert "tool-escalation" in decision.categories
