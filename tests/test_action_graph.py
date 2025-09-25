from packages.obs.action_graph import simple_linear_graph


def test_simple_linear_graph_shape():
    graph = simple_linear_graph(["overhear", "team", "plan"])
    assert len(graph["action_graph"]["nodes"]) == 3
    assert graph["action_graph"]["edges"] == [
        {"source": "n0", "target": "n1"},
        {"source": "n1", "target": "n2"},
    ]
    assert graph["component_graph"] == {"nodes": [], "edges": []}
