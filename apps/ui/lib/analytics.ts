export async function trackEvent(event: string, metadata: Record<string, unknown> = {}): Promise<void> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const sessionId = getSessionId();
  try {
    await fetch(`${apiBase}/analytics/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, session_id: sessionId, metadata }),
    });
  } catch {
    // best-effort analytics
  }
}

function getSessionId(): string {
  const key = "overhearops_session_id";
  if (typeof window === "undefined") {
    return "server";
  }
  const existing = window.localStorage.getItem(key);
  if (existing) {
    return existing;
  }
  const generated = `sess-${Math.random().toString(16).slice(2, 10)}`;
  window.localStorage.setItem(key, generated);
  return generated;
}
