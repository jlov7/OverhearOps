"use client";

import { useEffect, useState } from "react";

import { trackEvent } from "../../lib/analytics";
import { normalizeLocale, t, type Locale } from "../../lib/i18n";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function AdminPage() {
  const [locale, setLocale] = useState<Locale>("en");
  const [settingsJson, setSettingsJson] = useState("{}");
  const [promptsJson, setPromptsJson] = useState("{}");
  const [policiesJson, setPoliciesJson] = useState("{}");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setLocale(normalizeLocale(window.localStorage.getItem("overhearops_locale")));
    }
    void trackEvent("admin_view");
    void loadAll();
  }, []);

  async function loadAll(): Promise<void> {
    const [settings, prompts, policies] = await Promise.all([
      fetch(`${API_BASE}/admin/settings`).then((r) => r.json()),
      fetch(`${API_BASE}/admin/prompts`).then((r) => r.json()),
      fetch(`${API_BASE}/admin/policies`).then((r) => r.json()),
    ]);
    setSettingsJson(JSON.stringify(settings, null, 2));
    setPromptsJson(JSON.stringify(prompts, null, 2));
    setPoliciesJson(JSON.stringify(policies, null, 2));
  }

  async function save(path: string, raw: string): Promise<void> {
    setMessage("");
    try {
      const payload = JSON.parse(raw) as Record<string, unknown>;
      const response = await fetch(`${API_BASE}${path}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload }),
      });
      if (!response.ok) {
        throw new Error(`Failed: ${response.status}`);
      }
      setMessage(`Saved ${path}`);
      void trackEvent("admin_save", { path });
    } catch (error) {
      setMessage(`Save failed: ${String(error)}`);
    }
  }

  async function applyPreset(preset: "speed" | "safety" | "cost"): Promise<void> {
    const response = await fetch(`${API_BASE}/admin/strategy/${preset}`, { method: "POST" });
    if (response.ok) {
      setMessage(`Strategy preset set to ${preset}`);
      void loadAll();
    } else {
      setMessage(`Failed to set strategy preset: ${response.status}`);
    }
  }

  return (
    <main style={{ padding: 16, display: "grid", gap: 16 }}>
      <h1>{t(locale, "admin")}</h1>
      <section style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button onClick={() => void applyPreset("speed")}>Preset: speed</button>
        <button onClick={() => void applyPreset("safety")}>Preset: safety</button>
        <button onClick={() => void applyPreset("cost")}>Preset: cost</button>
      </section>
      {message ? <p>{message}</p> : null}

      <Editor
        title={t(locale, "settings")}
        value={settingsJson}
        onChange={setSettingsJson}
        onSave={() => void save("/admin/settings", settingsJson)}
      />
      <Editor
        title={t(locale, "prompts")}
        value={promptsJson}
        onChange={setPromptsJson}
        onSave={() => void save("/admin/prompts", promptsJson)}
      />
      <Editor
        title={t(locale, "policies")}
        value={policiesJson}
        onChange={setPoliciesJson}
        onSave={() => void save("/admin/policies", policiesJson)}
      />
    </main>
  );
}

function Editor({
  title,
  value,
  onChange,
  onSave,
}: {
  title: string;
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
}) {
  return (
    <section style={{ border: "1px solid #d1d5db", borderRadius: 8, padding: 12, display: "grid", gap: 8 }}>
      <h2 style={{ margin: 0 }}>{title}</h2>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={`${title} editor`}
        style={{ width: "100%", minHeight: 220, fontFamily: "monospace", fontSize: 13 }}
      />
      <button onClick={onSave}>Save</button>
    </section>
  );
}
