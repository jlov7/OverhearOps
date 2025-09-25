"use client";

import cytoscape from "cytoscape";
import { useEffect, useRef } from "react";

type GraphData = {
  action_graph: { nodes: Array<{ id: string; label: string }>; edges: Array<{ source: string; target: string }> };
};

export default function Graph({ data }: { data: GraphData }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) {
      return undefined;
    }
    const cy = cytoscape({
      container: ref.current,
      elements: [
        ...data.action_graph.nodes.map((node) => ({ data: { id: node.id, label: node.label } })),
        ...data.action_graph.edges.map((edge) => ({ data: { source: edge.source, target: edge.target } })),
      ],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": "#2563eb",
            color: "#fff",
            "font-size": 14,
            width: 96,
            height: 36,
            "border-color": "#1d4ed8",
            "border-width": 2,
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#94a3b8",
            "target-arrow-color": "#94a3b8",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
          },
        },
      ],
    });
    // Breadthfirst layout keeps the overhear -> ship chain readable (Cytoscape.js layouts guide).
    cy.layout({ name: "breadthfirst", fit: true, padding: 20 }).run();

    return () => {
      cy.destroy();
    };
  }, [data]);

  return <div ref={ref} style={{ height: "58vh", border: "1px solid #e5e7eb", borderRadius: 12 }} />;
}
