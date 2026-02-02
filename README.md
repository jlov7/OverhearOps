# OverhearOps

OverhearOps is a local, demo-ready agentic system that “overhears” Teams-shaped conversations, detects actionable threads, spins up a micro-team, and drafts dry-run remediation artefacts with full observability, safety controls, and replay.

## Getting started
1. **Prerequisites:** Install [uv](https://docs.astral.sh/uv/), Python 3.12, Node 20+, Docker Desktop (for the OTEL stack), and ensure `npm` is available.
2. **Bootstrap dependencies:** Run `uv sync` to create the virtual environment, then `npm install` inside `apps/ui` if this is your first checkout.
3. **Environment file:** Copy `.env.example` to `.env`, keep `ADAPTER=demo` for NDJSON mode, and set OTEL or branch width overrides as needed. Leave the Microsoft Graph secrets blank until you are ready to switch to `ADAPTER=graph`. Default LLM mode is `offline` (fixtures).
4. **Run the stack:** Use `uv run task dev` (details below) to launch FastAPI, the Next.js UI, and the local OTEL collector in one go.
5. **First run:** Visit `http://localhost:3000`, press **Suggest Plans**, then open the Governance modal to confirm trace IDs, branch count, and replay hash appear. Jaeger (`http://localhost:16686`) should show the run spans.
6. **Graph or Playground modes:** When you have tenant access, set `ADAPTER=graph` and provide `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`. For demo sharing without creds, flip to `ADAPTER=playground` and copy the sample Adaptive Card into the Microsoft 365 Agents Playground.

## 60-second demo flow
1. `uv run task dev` to launch FastAPI backend, Next.js UI, and OTEL stack.
2. Visit `http://localhost:3000` to load the Teams-style thread player.
3. Click **Suggest Plans** once the CI flake conversation appears; watch plan branches, judge decision, and shipped artefacts populate.
4. Inspect `/run/{id}` for action graph visualisation, safety ribbon, and open the Governance modal for trace IDs + replay hash.
5. Optional: `uv run task replay --seed=42` to deterministically regenerate agent spans.

## Explain like I’m a PM
- **Governance modal:** Surfaces trace IDs, branch count, replay hash, and reproduce command.
- **Confidence ribbon:** Shows confidence, approximate token cost, and run time from span data.
- **Attack surface:** Safety banner lists categories triggered by the guard.

- **What it does:** Listens to release chatter and proposes mitigation strategies, picks a winner, and hands you a ready-to-send PR diff + Jira stub.
- **Why you care:** Saves triage time, documents options for release management, and keeps a safety watchdog on prompt-injection tricks.
- **How it stays transparent:** Every decision is traced via OpenTelemetry, surfaced as action/component graphs, and replayable.

## One-command run
```bash
uv run task dev
```

Ensure Node 20+ and Docker are available. The command boots the backend (port 8000), UI (port 3000), and OTEL collector/Grafana.

## Adapter modes
- `ADAPTER=demo` (default): Streams Teams-shaped NDJSON from `data/demo/threads`.
- `ADAPTER=graph`: Wires the Microsoft Graph seam; without credentials the service raises an informative error rather than silently failing.
- `ADAPTER=playground`: Keeps the demo offline but exposes `GET /playground/card/plan` so you can paste an Adaptive Card into the Microsoft 365 Agents Playground.

## LLM modes
- `OVERHEAROPS_LLM_MODE=offline` (default): Use deterministic fixtures under `data/demo/llm`.
- `OVERHEAROPS_LLM_MODE=record`: Call live provider and store responses for replay.
- `OVERHEAROPS_LLM_MODE=replay`: Use stored responses for deterministic playback.
- `OVERHEAROPS_LLM_MODE=live`: Call the configured provider directly (costs apply).

Set `OVERHEAROPS_LLM_PROVIDER` to label the provider in run payloads (defaults to `offline`).

### Agents Playground plan card
```json
{
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "type": "AdaptiveCard",
  "version": "1.5",
  "body": [
    { "type": "TextBlock", "text": "OverhearOps Plan B", "weight": "Bolder", "size": "Medium" },
    { "type": "TextBlock", "text": "Increase timeout to 120s on Windows", "wrap": true },
    {
      "type": "FactSet",
      "facts": [
        { "title": "Confidence", "value": "0.74" },
        { "title": "Estimated cost", "value": "~3.2k tokens" },
        { "title": "Blast radius", "value": "Low" }
      ]
    }
  ],
  "actions": [
    { "type": "Action.Submit", "title": "Ship (dry-run)", "data": { "action": "ship_plan_b" } },
    { "type": "Action.Submit", "title": "Show Diff", "data": { "action": "show_diff" } }
  ]
}
```

## Governance & safety
- **Traces:** Dual OTEL exporters send spans to OTLP backends and `runs/{run_id}/spans.jsonl` so the UI can render derived graphs.
- **Replay:** `task replay --seed=42` reproduces branch decisions and checks the stored `hash.txt` derived from span timelines.
- **Abstain:** The uncertainty gate refuses to ship artefacts if confidence drops below threshold; UI ribbons flag blocked runs.
- **Prompt-injection defence:** Rule-based Coordinator + Guard blocks the 8x5 attack suite (ASR = 0) and redacts secrets before artefacts ship.

## Directory highlights
- `apps/service`: FastAPI entrypoint, Teams adapter, replay scheduler.
- `packages/agentkit`: LangGraph 1.0 StateGraph nodes (overhear → ship).
- `packages/obs`: OpenTelemetry bootstrap, action graph builder, safety pipeline.
- `apps/ui`: Next.js Teams-style UI with AdaptiveCard-like kit and Cytoscape visualisation.
- `infra`: Local OTEL collector, Tempo, Grafana.
- `tests`: Unit, e2e, and replay determinism checks.

## Observability setup
Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` and `OTEL_SERVICE_NAME=overhearops`. The service also writes spans to `runs/{id}/spans.jsonl`, derives `graphs.json`, and surfaces replay hashes in the UI. Grafana (http://localhost:3001) ships with Tempo datasource preconfigured.

## Sending traces to LangSmith or Langfuse
- **LangSmith:** Point `OTEL_EXPORTER_OTLP_ENDPOINT` to the LangSmith OTLP endpoint and set `OTEL_EXPORTER_OTLP_HEADERS` with your API key (`x-api-key=...`).
- **Langfuse:** Follow https://langfuse.com/integrations/native/opentelemetry and update endpoint + headers accordingly.
