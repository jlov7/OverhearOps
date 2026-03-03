"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { trackEvent } from "../../lib/analytics";
import { normalizeLocale, t, type Locale } from "../../lib/i18n";

type RunSummary = {
  run_id: string;
  thread_id: string;
  status: string;
  winner_plan_id: string;
  action: string;
  certainty?: number;
  replay_hash: string;
  updated_at_ms: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function HistoryPage() {
  const [locale, setLocale] = useState<Locale>("en");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<RunSummary[]>([]);
  const [leftRun, setLeftRun] = useState("");
  const [rightRun, setRightRun] = useState("");
  const [comparison, setComparison] = useState<Record<string, { left: unknown; right: unknown }> | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);
    if (search) params.set("q", search);
    params.set("limit", "100");
    return params.toString();
  }, [statusFilter, search]);

  const loadHistory = useCallback(async (): Promise<void> => {
    const response = await fetch(`${API_BASE}/runs/history?${query}`);
    const payload = (await response.json()) as { items: RunSummary[] };
    setItems(payload.items || []);
  }, [query]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setLocale(normalizeLocale(window.localStorage.getItem("overhearops_locale")));
    }
    void trackEvent("history_view");
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  async function compareSelected(): Promise<void> {
    if (!leftRun || !rightRun) {
      return;
    }
    const response = await fetch(`${API_BASE}/runs/compare?left=${encodeURIComponent(leftRun)}&right=${encodeURIComponent(rightRun)}`);
    const payload = (await response.json()) as { diff: Record<string, { left: unknown; right: unknown }> };
    setComparison(payload.diff);
    void trackEvent("history_compare", { left_run: leftRun, right_run: rightRun });
  }

  function exportJsonl(): void {
    window.open(`${API_BASE}/runs/export?format=jsonl`, "_blank", "noopener,noreferrer");
  }

  return (
    <main style={{ padding: 16, display: "grid", gap: 16 }}>
      <h1>{t(locale, "run_history")}</h1>
      <section style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <label htmlFor="status-filter">{t(locale, "filters")}</label>
        <select
          id="status-filter"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          aria-label="Status filter"
        >
          <option value="">All statuses</option>
          <option value="queued">queued</option>
          <option value="running">running</option>
          <option value="succeeded">succeeded</option>
          <option value="failed">failed</option>
          <option value="cancelled">cancelled</option>
          <option value="timed_out">timed_out</option>
        </select>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search run/thread/plan"
          aria-label="Search history"
        />
        <button onClick={() => void loadHistory()}>{t(locale, "filters")}</button>
        <button onClick={exportJsonl}>{t(locale, "export_jsonl")}</button>
      </section>

      <section style={{ border: "1px solid #d1d5db", borderRadius: 8, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead style={{ background: "#f8fafc" }}>
            <tr>
              <th style={{ textAlign: "left", padding: 8 }}>Run ID</th>
              <th style={{ textAlign: "left", padding: 8 }}>Thread</th>
              <th style={{ textAlign: "left", padding: 8 }}>Status</th>
              <th style={{ textAlign: "left", padding: 8 }}>Winner</th>
              <th style={{ textAlign: "left", padding: 8 }}>Action</th>
              <th style={{ textAlign: "left", padding: 8 }}>Updated</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.run_id} style={{ borderTop: "1px solid #e5e7eb" }}>
                <td style={{ padding: 8 }}>
                  <a href={`/run/${encodeURIComponent(item.run_id)}`}>{item.run_id}</a>
                </td>
                <td style={{ padding: 8 }}>{item.thread_id}</td>
                <td style={{ padding: 8 }}>{item.status}</td>
                <td style={{ padding: 8 }}>{item.winner_plan_id}</td>
                <td style={{ padding: 8 }}>{item.action}</td>
                <td style={{ padding: 8 }}>{new Date(item.updated_at_ms).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section style={{ display: "grid", gap: 8, border: "1px solid #d1d5db", borderRadius: 8, padding: 12 }}>
        <h2 style={{ margin: 0 }}>{t(locale, "compare_runs")}</h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select value={leftRun} onChange={(event) => setLeftRun(event.target.value)} aria-label="Left run">
            <option value="">Select left run</option>
            {items.map((item) => (
              <option key={`left-${item.run_id}`} value={item.run_id}>
                {item.run_id}
              </option>
            ))}
          </select>
          <select value={rightRun} onChange={(event) => setRightRun(event.target.value)} aria-label="Right run">
            <option value="">Select right run</option>
            {items.map((item) => (
              <option key={`right-${item.run_id}`} value={item.run_id}>
                {item.run_id}
              </option>
            ))}
          </select>
          <button onClick={() => void compareSelected()}>{t(locale, "compare_runs")}</button>
        </div>
        {comparison ? (
          <pre style={{ maxHeight: "40vh", overflow: "auto", margin: 0 }}>
            {JSON.stringify(comparison, null, 2)}
          </pre>
        ) : null}
      </section>
    </main>
  );
}
