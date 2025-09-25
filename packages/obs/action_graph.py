def simple_linear_graph(nodes):
    ids = [f"n{i}" for i, _ in enumerate(nodes)]
    return {
        "action_graph": {
            "nodes": [{"id": ids[i], "label": name} for i, name in enumerate(nodes)],
            "edges": [
                {"source": ids[i], "target": ids[i + 1]} for i in range(len(ids) - 1)
            ],
        },
        "component_graph": {"nodes": [], "edges": []},
    }
