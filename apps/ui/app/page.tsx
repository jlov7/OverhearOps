"use client";

import { useEffect, useMemo, useState } from "react";

import { trackEvent } from "../lib/analytics";
import { normalizeLocale, t, type Locale } from "../lib/i18n";

type ChatMsg = {
  id: string;
  replyToId: string | null;
  createdDateTime: string;
  from: { user: { displayName: string } };
  body: { content: string };
};

export default function Home() {
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [threads, setThreads] = useState<string[]>([]);
  const [threadId, setThreadId] = useState("ci_flake");
  const [locale, setLocale] = useState<Locale>("en");

  const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

  useEffect(() => {
    if (typeof window !== "undefined") {
      setLocale(normalizeLocale(window.localStorage.getItem("overhearops_locale")));
    }
    void trackEvent("home_view");
  }, []);

  useEffect(() => {
    let active = true;
    async function loadThreads() {
      try {
        const res = await fetch(`${apiBase}/threads`);
        if (!res.ok) return;
        const data = (await res.json()) as Record<string, number>;
        const ids = Object.keys(data);
        if (active && ids.length) {
          setThreads(ids);
          setThreadId((current) => (ids.includes(current) ? current : ids[0]));
        }
      } catch {
        // best-effort for demo mode
      }
    }
    void loadThreads();
    return () => {
      active = false;
    };
  }, [apiBase]);

  useEffect(() => {
    if (!threadId) return;
    const ws = new WebSocket(`${apiBase.replace("http", "ws")}/stream/${threadId}`);
    ws.onmessage = (event) => {
      const parsed = JSON.parse(event.data) as ChatMsg;
      setMsgs((prev) => [...prev, parsed]);
    };
    return () => ws.close();
  }, [apiBase, threadId]);

  const thread = useMemo(
    () => [...msgs].sort((a, b) => a.createdDateTime.localeCompare(b.createdDateTime)),
    [msgs],
  );

  async function suggestPlans() {
    setLoading(true);
    void trackEvent("suggest_plans_clicked", { thread_id: threadId });
    const response = await fetch(`${apiBase}/run/${threadId}`, { method: "POST" });
    const data = (await response.json()) as { run_id: string; verdict: unknown };
    sessionStorage.setItem("last_verdict", JSON.stringify(data.verdict));
    window.location.href = `/run/${encodeURIComponent(data.run_id)}`;
  }

  function updateLocale(next: Locale): void {
    setLocale(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("overhearops_locale", next);
    }
  }

  return (
    <main style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 16, padding: 16 }}>
      <section aria-label="Thread panel">
        <h1>{t(locale, "app_title")}</h1>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <label htmlFor="thread-select" style={{ fontSize: 12, color: "#666" }}>
            {t(locale, "thread")}
          </label>
          <select
            id="thread-select"
            value={threadId}
            aria-label="Thread selector"
            onChange={(event) => {
              setMsgs([]);
              setThreadId(event.target.value);
            }}
            style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #ddd" }}
          >
            {(threads.length ? threads : ["ci_flake"]).map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>

          <label htmlFor="locale-select" style={{ fontSize: 12, color: "#666" }}>
            Locale
          </label>
          <select
            id="locale-select"
            value={locale}
            aria-label="Locale selector"
            onChange={(event) => updateLocale(normalizeLocale(event.target.value))}
            style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #ddd" }}
          >
            <option value="en">English</option>
            <option value="es">Español</option>
          </select>
        </div>
        <div
          style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12, height: "72vh", overflow: "auto" }}
          role="log"
          aria-live="polite"
        >
          {thread.map((msg) => (
            <article key={msg.id} style={{ padding: 8, borderBottom: "1px solid #eee" }}>
              <div style={{ fontWeight: 600 }}>
                {msg.from.user.displayName}
                <span style={{ fontWeight: 400, color: "#666", marginLeft: 8 }}>
                  {new Date(msg.createdDateTime).toLocaleTimeString()}
                </span>
              </div>
              <div style={{ whiteSpace: "pre-wrap" }}>{msg.body.content}</div>
            </article>
          ))}
        </div>
      </section>
      <aside aria-label="Actions and facts">
        <button
          onClick={suggestPlans}
          disabled={loading}
          aria-busy={loading}
          style={{ width: "100%", padding: 12, borderRadius: 8, fontSize: 16 }}
        >
          {loading ? t(locale, "thinking") : t(locale, "suggest_plans")}
        </button>
        <p style={{ fontSize: 12, color: "#666", marginTop: 8 }}>
          Plays a Teams-shaped thread and invokes the OverhearOps pipeline.
        </p>
        <Facts
          title="What’s happening?"
          facts={[
            ["Paradigm", "Overhearing (listen-first)"],
            ["Runtime", "LangGraph 1.0 (durable)"],
            ["Safety", "Coordinator+Guard"],
            ["Observability", "OpenTelemetry (OTLP)"],
            ["Mode", "Offline (fixtures)"],
          ]}
        />
      </aside>
    </main>
  );
}

function Facts({ title, facts }: { title: string; facts: [string, string][] }) {
  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12, marginTop: 12 }}>
      <div style={{ fontWeight: 600 }}>{title}</div>
      <ul style={{ paddingLeft: 16, marginTop: 8 }}>
        {facts.map(([label, value]) => (
          <li key={label}>
            <b>{label}:</b> {value}
          </li>
        ))}
      </ul>
    </div>
  );
}
