from packages.obs.defence import ATTACK_CASES, run_defence


def test_adversarial_strings_are_blocked() -> None:
    blocked = 0
    for payload in ATTACK_CASES[:10]:
        prompt = str(payload["prompt"])
        decision = run_defence(prompt)
        if not decision.allowed:
            blocked += 1
    assert blocked == 10


def test_adversarial_pack_reports_categories() -> None:
    payload = ATTACK_CASES[0]["prompt"]
    decision = run_defence(payload)
    assert decision.categories
    assert decision.justification.startswith("Blocked:")
