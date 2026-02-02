from packages.agentkit.provider import OfflineProvider


def test_offline_provider_reads_fixture():
    provider = OfflineProvider(base_dir="data/demo/llm")
    output = provider.generate_json(task="plan", thread_id="ci_flake")
    assert output[0]["id"] == "plan-quarantine"
