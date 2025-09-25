# OverhearOps

OverhearOps is a local, demo-ready agentic system that “overhears” Teams-shaped conversations, detects actionable threads, spins up a micro-team, and drafts dry-run remediation artefacts with full observability, safety controls, and replay.

## 60-second demo flow
1. `uv run task dev` to launch FastAPI backend, Next.js UI, and OTEL stack.
2. Visit `http://localhost:3000` to load the Teams-style thread player.
3. Click **Suggest Plans** once the CI flake conversation appears; watch plan branches, judge decision, and shipped artefacts populate.
4. Inspect `/run/{id}` for timeline, action graph visualisation, and safety report.
5. Optional: `uv run task replay --seed=42` to deterministically regenerate agent spans.

## Explain like I’m a PM
- **What it does:** Listens to release chatter and proposes three mitigation strategies, picks a winner, and hands you a ready-to-send PR diff + Jira stub.
- **Why you care:** Saves triage time, documents options for release management, and keeps a safety watchdog on prompt-injection tricks.
- **How it stays transparent:** Every decision is traced via OpenTelemetry, surfaced as action/component graphs, and replayable.

## One-command run
```bash
uv run task dev
```

Ensure Node 20+ and Docker are available. The command boots the backend (port 8000), UI (port 3000), and OTEL collector/Grafana.

## Governance & safety
- **Traces:** All nodes emit OTEL spans with run IDs; the UI persists graphs under `runs/{run_id}` for auditing.
- **Replay:** `task replay --seed=42` reproduces the same branch decisions to validate determinism.
- **Abstain:** The uncertainty gate refuses to ship artefacts if self-consistency drops below threshold; UI surfaces abstentions.
- **Prompt-injection defence:** Coordinator + Guard pipeline classifies attacks, redacts responses, and logs mitigations. Mini attack suite ensures ASR \~0.

## Directory highlights
- `apps/service`: FastAPI entrypoint, Teams adapter, replay scheduler.
- `packages/agentkit`: LangGraph 1.0 StateGraph nodes (overhear → ship).
- `packages/obs`: OpenTelemetry bootstrap, action graph builder, safety pipeline.
- `apps/ui`: Next.js Teams-style UI with AdaptiveCard-like kit and Cytoscape visualisation.
- `infra`: Local OTEL collector, Tempo, Grafana.
- `tests`: Unit, e2e, and replay determinism checks.

## Observability setup
Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` and `OTEL_SERVICE_NAME=overhearops`. Grafana (http://localhost:3001) ships with Tempo datasource preconfigured.

## Sending traces to LangSmith or Langfuse
- **LangSmith:** Point `OTEL_EXPORTER_OTLP_ENDPOINT` to the LangSmith OTLP endpoint and set `OTEL_EXPORTER_OTLP_HEADERS` with your API key (`x-api-key=...`).
- **Langfuse:** Follow https://langfuse.com/integrations/native/opentelemetry and update endpoint + headers accordingly.
