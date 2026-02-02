"use client";

import { useEffect, useMemo, useState } from "react";

import Graph from "../../../components/Graph";
import Modal from "../../../components/Modal";
import Ribbon from "../../../components/Ribbon";

type RunPayload = {
  verdict: any;
  artefacts: any;
  plans?: any[];
  replay_hash?: string;
  artefacts_by_plan?: Record<string, any>;
  gate?: { action?: string; certainty?: number };
  provider?: string;
  mode?: string;
  thread_id?: string;
};

type GraphPayload = {
  action_graph: {
    nodes: Array<{ id: string; label: string; trace_id?: string; t0?: number; t1?: number; attrs?: Record<string, any> }>;
    edges: Array<{ source: string; target: string }>;
  };
  component_graph: {
    nodes: Array<{ id: string; label: string; items?: string[] }>;
    edges: Array<{ source: string; target: string }>;
  };
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function RunPage({ params }: { params: { id: string } }) {
  const runId = decodeURIComponent(params.id);
  const [data, setData] = useState<RunPayload | null>(null);
  const [graphs, setGraphs] = useState<GraphPayload | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [showGovernance, setShowGovernance] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [showJira, setShowJira] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [artefactRes, graphRes] = await Promise.all([
          fetch(`${API_BASE}/runs/${runId}`),
          fetch(`${API_BASE}/runs/${runId}/graphs.json`),
        ]);
        const artefacts = (await artefactRes.json()) as RunPayload;
        const graphData = (await graphRes.json()) as GraphPayload;
        if (!cancelled) {
          setData(artefacts);
          setGraphs(graphData);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const plans = data?.plans ?? [];
  const winnerPlanId = data?.verdict?.winner_plan_id ?? data?.verdict?.winner?.plan?.id;
  const winnerPlan = plans.find((plan) => plan.id === winnerPlanId) ?? data?.verdict?.winner?.plan ?? null;
  const safety = data?.artefacts?.safety;
  const categories = safety?.categories ?? [];
  const safetyPassed = safety ? Boolean(safety.allowed) : true;
  const hasDiff = Boolean(data?.artefacts?.pr_diff);
  const hasJira = !!(data?.artefacts?.jira && Object.keys(data.artefacts.jira).length);
  const gateAction = data?.gate?.action ?? data?.verdict?.action;
  const gateCertainty = data?.gate?.certainty ?? data?.verdict?.certainty;

  const metrics = useMemo(() => {
    if (!graphs) {
      return { tokenCost: undefined, durationMs: undefined, traceIds: [] as string[] };
    }
    const nodes = graphs.action_graph.nodes;
    const tokenCost = nodes.reduce((total, node) => {
      const attrs = node.attrs ?? {};
      const inbound = Number(attrs["token.approx_in"] ?? 0);
      const outbound = Number(attrs["token.approx_out"] ?? 0);
      return total + inbound + outbound;
    }, 0);
    const times = nodes
      .map((node) => Number(node.t0 ?? 0))
      .concat(nodes.map((node) => Number(node.t1 ?? 0)))
      .filter((value) => Number.isFinite(value) && value > 0);
    const minTime = times.length ? Math.min(...times) : undefined;
    const maxTime = times.length ? Math.max(...times) : undefined;
    const durationMs = minTime !== undefined && maxTime !== undefined ? (maxTime - minTime) / 1_000_000 : undefined;
    const traceIds = Array.from(new Set(nodes.map((node) => node.trace_id).filter(Boolean))) as string[];
    return { tokenCost, durationMs, traceIds };
  }, [graphs]);

  const branchCount = plans.length;
  const replayHash = data?.replay_hash ?? "";
  const reproduceCommand = `uv run apps/service/replay.py --thread ${data?.thread_id ?? "ci_flake"} --seed 42`;

  return (
    <main style={{ display: "grid", gap: 16, padding: 16 }}>
      <Ribbon confidence={winnerPlan?.confidence} costTokens={metrics.tokenCost} durationMs={metrics.durationMs} />

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
        }}
      >
        <div style={{ display: "grid", gap: 12 }}>
          <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>Plan & Decision</h2>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" onClick={() => setShowDiff(true)} disabled={!hasDiff}>
                View PR diff
              </button>
              <button type="button" onClick={() => setShowJira(true)} disabled={!hasJira}>
                View Jira stub
              </button>
              <button type="button" onClick={() => setShowGovernance(true)}>
                Governance
              </button>
            </div>
          </header>

          <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 16, background: "#f8fafc" }}>
            {loading && <p>Loading run summary...</p>}
            {!loading && data && (
              <>
                <p style={{ marginTop: 0 }}>
                  <strong>Winner:</strong> {winnerPlan?.id} - {winnerPlan?.title}
                </p>
                <p>
                  <strong>Gate:</strong> {gateAction ?? "pending"}{" "}
                  {gateCertainty !== undefined ? `(${gateCertainty.toFixed(2)})` : ""}
                </p>
                <p>
                  <strong>Hypothesis:</strong> {winnerPlan?.hypothesis}
                </p>
                <p>
                  <strong>Rationale:</strong> {data.verdict?.rationale}
                </p>
                <p>
                  <strong>Uncertainty:</strong> {data.verdict?.uncertainty}
                </p>
                {Array.isArray(winnerPlan?.steps) && winnerPlan.steps.length ? (
                  <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                    {winnerPlan.steps.map((step: string, index: number) => (
                      <li key={index}>{step}</li>
                    ))}
                  </ul>
                ) : null}
                <div
                  style={{
                    borderRadius: 10,
                    padding: 12,
                    marginTop: 12,
                    background: safetyPassed ? "rgba(22,163,74,0.12)" : "rgba(220,38,38,0.12)",
                    color: safetyPassed ? "#166534" : "#991b1b",
                  }}
                >
                  <strong>Safety</strong>: {safetyPassed ? "Passed" : "Blocked"} - {safety?.justification ?? "Guard active"}
                  {categories.length ? <span> ({categories.join(", ")})</span> : null}
                </div>
              </>
            )}
          </div>
          {plans.length ? (
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 16, background: "#fff" }}>
              <h3 style={{ marginTop: 0 }}>All Plans</h3>
              <div style={{ display: "grid", gap: 12 }}>
                {plans.map((plan) => (
                  <div
                    key={plan.id}
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: 10,
                      padding: 12,
                      background: plan.id === winnerPlanId ? "rgba(37,99,235,0.08)" : "#fff",
                    }}
                  >
                    <strong>
                      {plan.id} — {plan.title}
                    </strong>
                    <div style={{ fontSize: 13, color: "#475569", marginTop: 4 }}>
                      Confidence: {plan.confidence ?? "-"} · Blast radius: {plan.blast_radius ?? "-"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div style={{ display: "grid", gap: 12 }}>
          <h2 style={{ margin: 0 }}>Action Graph</h2>
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 12, background: "#fff" }}>
            {graphs ? <Graph data={graphs} /> : <p>Graph will appear once spans are available.</p>}
          </div>
          <footer style={{ fontSize: 13, color: "#475569", display: "flex", gap: 16 }}>
            <span>Trace IDs: {metrics.traceIds.length ? metrics.traceIds.join(", ") : "-"}</span>
            <span>Branches observed: {branchCount}</span>
            <span>Replay hash: {replayHash || "pending"}</span>
          </footer>
        </div>
      </section>

      <section style={{ borderTop: "1px solid #e2e8f0", paddingTop: 12, fontSize: 13, color: "#475569" }}>
        <strong>Component graph</strong>: {graphs?.component_graph.nodes.length ? (
          graphs.component_graph.nodes.map((node) => `${node.label}: ${node.items?.join(", ") ?? "-"}`).join(" | ")
        ) : (
          <>Awaiting richer component annotations.</>
        )}
      </section>

      <Modal open={showGovernance} onClose={() => setShowGovernance(false)} title="Governance & Replay">
        <dl style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: 8 }}>
          <dt>Run ID</dt>
          <dd>{runId}</dd>
          <dt>Provider</dt>
          <dd>{data?.provider ?? "offline"} ({data?.mode ?? "offline"})</dd>
          <dt>Trace IDs</dt>
          <dd>{metrics.traceIds.length ? metrics.traceIds.join(", ") : "-"}</dd>
          <dt>Branch count</dt>
          <dd>{branchCount}</dd>
          <dt>Replay hash</dt>
          <dd style={{ fontFamily: "monospace" }}>{replayHash || "pending"}</dd>
          <dt>Reproduce</dt>
          <dd>
            <code>{reproduceCommand}</code>
          </dd>
        </dl>
        <p style={{ marginTop: 16, fontSize: 13, color: "#475569" }}>
          Deterministic replay uses the LangGraph durable execution path (SQLite checkpointer) and the span hash
          persisted in <code>runs/{runId}/hash.txt</code>.
        </p>
      </Modal>

      <Modal open={showDiff} onClose={() => setShowDiff(false)} title="Dry-run PR diff">
        <pre style={{ maxHeight: "60vh", overflowY: "auto" }}>{data?.artefacts?.pr_diff || "No diff available."}</pre>
      </Modal>

      <Modal open={showJira} onClose={() => setShowJira(false)} title="Jira stub">
        <pre style={{ maxHeight: "60vh", overflowY: "auto" }}>{JSON.stringify(data?.artefacts?.jira ?? {}, null, 2)}</pre>
      </Modal>
    </main>
  );
}
