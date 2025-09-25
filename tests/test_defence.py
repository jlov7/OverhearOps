from packages.obs.defence import ATTACK_SUITE, run_defence


def test_attack_suite_blocked():
    blocked = 0
    for attack in ATTACK_SUITE:
        decision = run_defence(attack["prompt"])
        if not decision.allowed:
            blocked += 1
    assert blocked == len(ATTACK_SUITE)
