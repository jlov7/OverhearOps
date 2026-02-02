from packages.obs.runtime import get_run_context, set_run_context


def test_run_context_roundtrip():
    set_run_context(run_id="run-123", mode="offline", provider="offline")
    ctx = get_run_context()
    assert ctx.run_id == "run-123"
    assert ctx.mode == "offline"
    assert ctx.provider == "offline"
