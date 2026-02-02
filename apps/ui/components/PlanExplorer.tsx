"use client";

import cytoscape from "cytoscape";
import { useEffect, useRef, useState } from "react";
import { AdaptiveCard, Container, TextBlock, ActionSet, PrimaryButton, FactSet } from "./AdaptiveKit";
import { withUISpan } from "../lib/otel";

type RunPayload = {
  run_id: string;
  plans: any[];
  verdict: any;
  gate: { action?: string; certainty?: number };
  graphs: { action_graph: unknown; component_graph: unknown };
  artefacts: any;
  artefacts_by_plan: Record<string, any>;
};

type PlanExplorerProps = {
  apiBase: string;
};

export function PlanExplorer({ apiBase }: PlanExplorerProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState<RunPayload | null>(null);
  const graphRef = useRef<HTMLDivElement | null>(null);

  const triggerRun = async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await withUISpan<RunPayload>("ui.fetch_run", async () => {
        const res = await fetch(`${apiBase}/run/ci_flake`, { method: "POST" });
        if (!res.ok) throw new Error(`Backend returned ${res.status}`);
        return res.json();
      });
      setRun(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!run || !graphRef.current) return;
    const elements = [] as cytoscape.ElementDefinition[];
    const actionGraph = run.graphs?.action_graph as { nodes: any[]; edges: any[] };
    if (actionGraph) {
      elements.push(...actionGraph.nodes, ...actionGraph.edges);
    }
    const instance = cytoscape({
      container: graphRef.current,
      elements,
      layout: { name: "breadthfirst", directed: true, padding: 10 },
      style: [
        { selector: "node", style: { label: "data(label)", "background-color": "#6264a7", color: "#fff" } },
        { selector: "edge", style: { width: 2, "target-arrow-shape": "triangle", "line-color": "#bcbcbc" } },
      ],
    });
    return () => {
      instance.destroy();
    };
  }, [run]);

  const plans = run?.plans ?? [];
  const judgement = run?.verdict;
  const uncertainty = run?.gate;

  return (
    <div className="section-card" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <Container>
        <AdaptiveCard>
          <TextBlock text="Generate remediations" weight="bolder" size="medium" />
          <TextBlock text="Run the OverhearOps pipeline on the current thread." size="small" />
          <ActionSet
            actions={[
              <PrimaryButton
                key="run"
                label={loading ? "Running..." : "Suggest Plans"}
                onClick={loading ? undefined : triggerRun}
                disabled={loading}
              />,
            ]}
          />
        </AdaptiveCard>
        {error && (
          <AdaptiveCard>
            <TextBlock text={`Error: ${error}`} weight="bolder" size="small" />
          </AdaptiveCard>
        )}
        {run && (
          <AdaptiveCard>
            <TextBlock text="Safety" weight="bolder" size="small" />
            <FactSet
              facts={[
                { title: "Action", value: String(run.gate?.action ?? "pending") },
                { title: "Certainty", value: String(run.gate?.certainty ?? "-") },
                { title: "Winner", value: String(run.verdict?.winner_plan_id ?? "-") },
              ]}
            />
            <a href={`/run/${run.run_id}`} style={{ fontSize: 12 }}>
              View run details
            </a>
          </AdaptiveCard>
        )}
        {plans.length > 0 && (
          <AdaptiveCard>
            <TextBlock text="Candidate plans" weight="bolder" size="medium" />
            {plans.map((plan) => (
              <div key={plan.plan_id} style={{ border: "1px solid #e1dfdd", borderRadius: 8, padding: 12, marginBottom: 8 }}>
                <TextBlock text={plan.title} weight="bolder" />
                <TextBlock text={`Confidence: ${(plan.confidence ?? 0).toFixed(2)}`} size="small" />
                <ul>
                  {plan.steps?.map((step: string) => (
                    <li key={step}>{step}</li>
                  ))}
                </ul>
                <TextBlock text={`Blast radius: ${plan.blast_radius}`} size="small" />
                {judgement?.winner_plan_id === plan.id && (
                  <TextBlock text="Selected by judge" weight="bolder" size="small" />
                )}
              </div>
            ))}
            {uncertainty && (
              <TextBlock text={`Gate decision: ${uncertainty.action ?? "-"} (${(uncertainty.certainty ?? 0).toFixed(2)})`} size="small" />
            )}
          </AdaptiveCard>
        )}
        <AdaptiveCard>
          <TextBlock text="Action graph" weight="bolder" size="medium" />
          <div ref={graphRef} style={{ height: 240, background: "#f7f7f7", borderRadius: 8 }}></div>
        </AdaptiveCard>
      </Container>
    </div>
  );
}
