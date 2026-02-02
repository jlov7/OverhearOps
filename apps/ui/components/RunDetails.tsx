"use client";

import cytoscape from "cytoscape";
import { useEffect, useRef } from "react";
import { AdaptiveCard, Container, TextBlock, FactSet, registerAdaptiveStyles } from "./AdaptiveKit";

export type RunDetailsProps = {
  run: {
    run_id: string;
    plans: any[];
    verdict: any;
    gate: { action?: string; certainty?: number };
    graphs: { action_graph: any; component_graph: any };
  };
};

export function RunDetails({ run }: RunDetailsProps) {
  const actionRef = useRef<HTMLDivElement | null>(null);
  const componentRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    registerAdaptiveStyles();
  }, []);

  useEffect(() => {
    if (!actionRef.current) return;
    const graph = cytoscape({
      container: actionRef.current,
      elements: [...(run.graphs.action_graph?.nodes ?? []), ...(run.graphs.action_graph?.edges ?? [])],
      layout: { name: "breadthfirst", directed: true, padding: 12 },
      style: [
        { selector: "node", style: { label: "data(label)", "background-color": "#0078d4", color: "#fff" } },
        { selector: "edge", style: { width: 2, "line-color": "#888", "target-arrow-shape": "triangle" } },
      ],
    });
    return () => graph.destroy();
  }, [run]);

  useEffect(() => {
    if (!componentRef.current) return;
    const graph = cytoscape({
      container: componentRef.current,
      elements: [
        ...(run.graphs.component_graph?.nodes ?? []),
        ...(run.graphs.component_graph?.edges ?? []),
      ],
      layout: { name: "cose", padding: 12 },
      style: [
        { selector: "node", style: { label: "data(label)", "background-color": "#6264a7", color: "#fff" } },
        { selector: "edge", style: { width: 2, "line-color": "#aaa", "target-arrow-shape": "triangle" } },
      ],
    });
    return () => graph.destroy();
  }, [run]);

  const plans = run.plans ?? [];
  const winner = run.verdict?.winner_plan_id;
  const uncertainty = run.gate;

  return (
    <Container>
      <AdaptiveCard>
        <TextBlock text={`Run ${run.run_id}`} weight="bolder" size="medium" />
        <FactSet
          facts={[
            { title: "Gate", value: run.gate?.action ?? "pending" },
            { title: "Certainty", value: `${(uncertainty?.certainty ?? 0).toFixed(2)}` },
          ]}
        />
      </AdaptiveCard>

      <AdaptiveCard>
        <TextBlock text="Plan cards" weight="bolder" size="medium" />
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {plans.map((plan) => (
            <div key={plan.plan_id} style={{ border: "1px solid #e1dfdd", borderRadius: 8, padding: 12 }}>
              <TextBlock text={plan.title} weight="bolder" />
              <TextBlock text={plan.hypothesis} size="small" />
              <div
                style={{
                  background: "#edebe9",
                  borderRadius: 8,
                  overflow: "hidden",
                  height: 8,
                  margin: "8px 0",
                }}
              >
                <div
                  style={{
                    width: `${Math.round((plan.confidence ?? 0) * 100)}%`,
                    background: plan.id === winner ? "#107c10" : "#6264a7",
                    height: "100%",
                  }}
                />
              </div>
              <ul>
                {plan.steps?.map((step: string) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
              <TextBlock text={`Blast radius: ${plan.blast_radius}`} size="small" />
              {plan.id === winner && <TextBlock text="Winner" weight="bolder" size="small" />}
            </div>
          ))}
        </div>
      </AdaptiveCard>

      <AdaptiveCard>
        <TextBlock text="Action graph" weight="bolder" size="medium" />
        <div ref={actionRef} style={{ height: 220 }} />
      </AdaptiveCard>

      <AdaptiveCard>
        <TextBlock text="Component graph" weight="bolder" size="medium" />
        <div ref={componentRef} style={{ height: 220 }} />
      </AdaptiveCard>
    </Container>
  );
}
