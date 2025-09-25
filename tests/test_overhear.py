from packages.agentkit.overhear import detect_intents_from_stream


def test_detect_ci_flake():
    intents, score = detect_intents_from_stream("CI failing with timeout on Windows")
    assert "ci_flake" in intents
    assert score > 0.5
