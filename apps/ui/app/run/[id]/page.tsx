"use client";
import { useEffect, useState } from "react";

export default function RunPage({ params }: { params: { id: string } }) {
  const runId = decodeURIComponent(params.id);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetch(`http://localhost:8000/runs/${runId}`).then((res) => res.json()).then(setData);
  }, [runId]);

  return (
    <main style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, padding: 16 }}>
      <section>
        <h2>Plans & Decision</h2>
        <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
          {data ? (
            <>
              <p>
                <b>Winner:</b> Plan {data.verdict?.winner?.plan?.id} — {data.verdict?.winner?.plan?.title}
              </p>
              <p>
                <b>Rationale:</b> {data.verdict?.rationale}
              </p>
              <p>
                <b>Uncertainty:</b> {data.verdict?.uncertainty}
              </p>
              <details>
                <summary>Dry-run PR diff</summary>
                <pre>{data.artefacts?.pr_diff}</pre>
              </details>
              <details>
                <summary>Jira summary</summary>
                <pre>{JSON.stringify(data.artefacts?.jira, null, 2)}</pre>
              </details>
            </>
          ) : (
            "Run details will appear here."
          )}
        </div>
      </section>
      <section>
        <h2>Trace & Action-graph</h2>
        <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12, height: "60vh", overflow: "auto" }}>
          <pre>{JSON.stringify(data?.action_graph, null, 2)}</pre>
        </div>
      </section>
    </main>
  );
}
