from fastapi.testclient import TestClient

from apps.service.main import app

EXPECTED_CHAIN = ["overhear", "team", "plan", "exec", "judge", "gate", "ship"]


def _is_subsequence(target: list[str], sequence: list[str]) -> bool:
    iterator = iter(sequence)
    return all(any(candidate == item for candidate in iterator) for item in target)


def test_graph_endpoint_returns_span_chain():
    with TestClient(app) as client:
        run_response = client.post("/run/ci_flake")
        assert run_response.status_code == 200
        run_id = run_response.json()["run_id"]

        graph_response = client.get(f"/runs/{run_id}/graphs.json")
        assert graph_response.status_code == 200
        payload = graph_response.json()

    action_graph = payload["action_graph"]
    nodes = action_graph["nodes"]
    edges = action_graph["edges"]

    assert len(nodes) >= len(EXPECTED_CHAIN)
    ordered = sorted(nodes, key=lambda node: node.get("t0", 0))
    labels = [node.get("label") for node in ordered]
    assert _is_subsequence(EXPECTED_CHAIN, labels)

    assert len(edges) >= len(EXPECTED_CHAIN) - 1
