# OverhearOps

OverhearOps is a local, demo-ready agentic system that “overhears” Teams-shaped conversations, detects actionable threads, spins up a micro-team, and drafts dry-run remediation artefacts with full observability, safety controls, and replay.

## Getting started
1. **Prerequisites:** Install [uv](https://docs.astral.sh/uv/), Python 3.12, Node 20+, Docker Desktop (for the OTEL stack), and ensure `npm` is available.
2. **Bootstrap dependencies:** Run `uv sync` to create the virtual environment, then `npm install` inside `apps/ui` if this is your first checkout.
3. **Environment file:** Copy `.env.example` to `.env`, keep `ADAPTER=demo` for NDJSON mode, and set OTEL or branch width overrides as needed. Leave the Microsoft Graph secrets blank until you are ready to switch to `ADAPTER=graph`. Default LLM mode is `offline` (fixtures).
4. **Run the stack:** Use `uv run task dev` (details below) to launch FastAPI, the Next.js UI, and the local OTEL collector in one go.
5. **First run:** Visit `http://localhost:3000`, pick the CI flake or security alert thread, press **Suggest Plans**, then open the Governance modal to confirm trace IDs, branch count, and replay hash appear. Jaeger (`http://localhost:16686`) should show the run spans.
6. **Graph or Playground modes:** When you have tenant access, set `ADAPTER=graph` and provide `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`. For demo sharing without creds, flip to `ADAPTER=playground` and copy the sample Adaptive Card into the Microsoft 365 Agents Playground.

## 60-second demo flow
1. `uv run task dev` to launch FastAPI backend, Next.js UI, and OTEL stack.
2. Visit `http://localhost:3000` to load the Teams-style thread player.
3. Click **Suggest Plans** once the CI flake or security alert conversation appears; watch plan branches, judge decision, and shipped artefacts populate.
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

Graph thread IDs support:
- `team_id:channel_id` for channel messages.
- `chat:chat_id` for chat messages.

## LLM modes
- `OVERHEAROPS_LLM_MODE=offline` (default): Use deterministic fixtures under `data/demo/llm`.
- `OVERHEAROPS_LLM_MODE=record`: Call live provider and store responses for replay.
- `OVERHEAROPS_LLM_MODE=replay`: Use stored responses for deterministic playback.
- `OVERHEAROPS_LLM_MODE=live`: Call the configured provider directly (costs apply).

Set `OVERHEAROPS_LLM_PROVIDER` to choose the provider:
- `offline` (default fixtures)
- `openai` (live/record modes via Responses API; requires `OPENAI_API_KEY`)

For OpenAI live modes, configure:
- `OPENAI_API_KEY`
- `OVERHEAROPS_OPENAI_MODEL` (default `gpt-5-mini`)
- `OVERHEAROPS_OPENAI_FALLBACK_MODEL` (optional failover model)
- `OVERHEAROPS_OPENAI_MAX_RETRIES` (default `2` for transient 408/409/429/5xx responses)
- `OVERHEAROPS_OPENAI_RETRY_BACKOFF_S` (default `0.5`, exponential backoff base)
- `OVERHEAROPS_OPENAI_CIRCUIT_FAILURES` (default `3`)
- `OVERHEAROPS_OPENAI_CIRCUIT_COOLDOWN_S` (default `30`)
- `OVERHEAROPS_EXTERNAL_MAX_RETRIES` / `OVERHEAROPS_EXTERNAL_RETRY_BACKOFF_S` for shared external-call defaults.
- `OVERHEAROPS_EXTERNAL_CIRCUIT_FAILURES` / `OVERHEAROPS_EXTERNAL_CIRCUIT_COOLDOWN_S` for shared circuit policy.
- `OPENAI_BASE_URL` (default `https://api.openai.com/v1`)

## Security and tenancy
- `OVERHEAROPS_SECURITY_MODE=off` (default): No token required (demo mode).
- `OVERHEAROPS_SECURITY_MODE=api_key`: Require `Authorization: Bearer <token>`.
- `OVERHEAROPS_AUTH_TOKENS_JSON`: JSON token map with role + tenant, for example:
  - `{"token-operator":{"role":"operator","tenant_id":"default","subject":"ops-user"},"token-approver":{"role":"approver","tenant_id":"default","subject":"lead"}}`
- `OVERHEAROPS_DEFAULT_TENANT` controls default tenant when no tenant header is provided.
- `X-OverhearOps-Tenant` header selects tenant context (admins can switch tenants).
- `OVERHEAROPS_INGEST_HMAC_SECRET` enables signed ingest checks for `POST /threads/{thread}/events` using:
  - `X-OverhearOps-Signature: sha256=<hex-hmac-of-request-body>`

## Run lifecycle API
- `POST /run/{thread_id}`: synchronous run execution (returns `{run_id, verdict}`).
- `POST /runs` with `{thread_id, background}`:
  - `background=false` runs inline and returns terminal status.
  - `background=true` persists to SQLite queue and returns HTTP 202.
- `POST /runs` supports `Idempotency-Key` header for safe retries.
- `POST /runs/{run_id}/cancel`: requests cancellation for queued/running runs.
- `GET /runs/{run_id}/status`: run state (`queued|running|cancel_requested|cancelled|succeeded|failed|timed_out`) with timing metadata.
- `GET /runs/{run_id}`: persisted run artefacts payload.
- `GET /runs/dlq`: tenant-scoped list of failed/timed-out jobs from queue storage.
- `POST /runs/{run_id}/replay`: enqueue a replay of a failed/timed-out run.
- `POST /runs/{run_id}/approve`: approver-role sign-off for live shipping.
- `GET /runs/{run_id}/approvals`: collaborative approval records.
- `POST /runs/{run_id}/ship`: applies side effects only in `OVERHEAROPS_INTEGRATION_MODE=live`, with approval enforcement.
- `POST /runs/{run_id}/simulate`: policy simulation check for shipping eligibility.
- `GET /runs/history`: tenant-scoped searchable run history.
- `GET /runs/compare?left=<id>&right=<id>`: run-level field diff.
- `GET /runs/export?format=json|jsonl`: export history.
- `GET /tenants/{tenant_id}/usage` and `GET /usage/export`: usage metering/billing hooks.
- `POST /analytics/events` and `GET /analytics/funnel`: product analytics funnel instrumentation.
- `GET/PUT /admin/settings`, `GET/PUT /admin/prompts`, `GET/PUT /admin/policies`, `POST /admin/strategy/{preset}`: admin settings surface and strategy presets.

Public probes:
- `GET /livez`
- `GET /readyz`
- `GET /status/public`

API version aliases:
- `GET /api/version`
- `GET /api/v1/*` for core health/thread/run endpoints.

Thread event ingestion is bounded by `OVERHEAROPS_MAX_THREAD_EVENTS` to avoid unbounded memory growth.
Run status cache is bounded by `OVERHEAROPS_MAX_RUN_STATUS`; latest status is persisted to `runs/{run_id}/status.json`.
Run timeouts are enforced by `OVERHEAROPS_RUN_MAX_RUNTIME_S` (default `600`).
Queue controls: `OVERHEAROPS_QUEUE_ENABLED`, `OVERHEAROPS_QUEUE_POLL_INTERVAL_S`, `OVERHEAROPS_QUEUE_LEASE_MS`.
Integration controls: `OVERHEAROPS_INTEGRATION_MODE=dry_run|live`, `OVERHEAROPS_REQUIRE_APPROVAL_FOR_SHIP`.
DSR skeleton endpoints:
- `GET /tenants/{tenant_id}/dsr/export` (admin role)
- `POST /tenants/{tenant_id}/dsr/delete` with `{"dry_run": true|false}` (admin role)

## Credential scopes
- `OVERHEAROPS_CREDENTIAL_SCOPE=dry_run` (default) uses `MS_DRYRUN_*` first, then falls back to `MS_*`.
- `OVERHEAROPS_CREDENTIAL_SCOPE=prod` requires `MS_PROD_*`.
- Keep dry-run and production app registrations separate to avoid cross-environment token reuse.

## Storage Security Hooks
- `OVERHEAROPS_STORAGE_CODEC=plain` (default) controls persisted JSON codec.
- `OVERHEAROPS_STORAGE_KEY_ID=<id>` writes sidecar metadata (`*.meta.json`) for key rotation tracking.
- This provides rotation hooks without forcing encryption in local demo mode.

## Retention cleanup
Use the cleanup utility to purge old runs:

```bash
uv run python scripts/cleanup_runs.py --max-age-hours 168 --keep-latest 200
```

Dry-run mode:

```bash
uv run python scripts/cleanup_runs.py --dry-run
```

List/replay failed jobs:

```bash
uv run python scripts/replay_dlq.py --token <operator_token>
uv run python scripts/replay_dlq.py --token <operator_token> --run-id <failed_run_id>
```

Backup/restore runtime state:

```bash
uv run python scripts/backup_restore.py backup --output backups/overhearops.tar.gz
uv run python scripts/backup_restore.py restore --archive backups/overhearops.tar.gz
```

Load/soak check:

```bash
uv run python scripts/load_soak.py --base-url http://localhost:8000 --concurrency 20 --requests-per-worker 50
```

Hard release gate:

```bash
./scripts/release_gate.sh
```

Canary + rollback:

```bash
uv run python scripts/canary_rollout.py
```

Benchmark scorecard:

```bash
uv run python scripts/benchmark_scorecard.py --output docs/ops/benchmark-scorecard.json
```

Integration health monitors:

```bash
uv run python scripts/integration_health_check.py
uv run python scripts/probe_public_status.py
```

Signed evidence bundles:

```bash
uv run python scripts/export_evidence_bundle.py --run-id <run_id>
```

## Demo threads
- `ci_flake`: pipeline timeout & test flakiness triage.
- `security_alert`: CVE response with rotation + hotfix plans.

## Demo smoke checklist
- `/threads` lists `ci_flake` + `security_alert`.
- Run detail view shows **Mode/Provider** badges and **Plans executed** count.
- `uv run pytest tests/test_determinism.py::test_determinism_offline -v` passes.
- `uv run pytest tests/test_security_scenario.py::test_security_thread_uses_security_fixtures -v` passes.

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
- **Policy-as-code:** Shipping/simulation checks are loaded from `config/policy_rules.json`.
- **Prompt registry:** Task prompts and selected versions are managed in `config/prompt_registry.json`.
- **Model routing:** Task-level model routing is managed in `config/runtime_settings.json`.

## UI surfaces
- `/`: live thread playback + run launch.
- `/run/{id}`: verdict, explainability, graphs, governance modal, trace links.
- `/history`: run history search/filter/export/compare.
- `/admin`: runtime settings, prompt registry, policies, strategy preset controls.

## Directory highlights
- `apps/service`: FastAPI entrypoint, Teams adapter, replay scheduler.
- `packages/agentkit`: LangGraph 1.0 StateGraph nodes (overhear → ship).
- `packages/obs`: OpenTelemetry bootstrap, action graph builder, safety pipeline.
- `apps/ui`: Next.js Teams-style UI with AdaptiveCard-like kit and Cytoscape visualisation.
- `infra`: Local OTEL collector, Tempo, Grafana.
- `tests`: Unit, e2e, replay determinism, and security scenario checks.

## Observability setup
Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` and `OTEL_SERVICE_NAME=overhearops`. The service also writes spans to `runs/{id}/spans.jsonl`, derives `graphs.json`, and surfaces replay hashes in the UI. Grafana (http://localhost:3001) ships with Tempo datasource preconfigured.

## Sending traces to LangSmith or Langfuse
- **LangSmith:** Point `OTEL_EXPORTER_OTLP_ENDPOINT` to the LangSmith OTLP endpoint and set `OTEL_EXPORTER_OTLP_HEADERS` with your API key (`x-api-key=...`).
- **Langfuse:** Follow https://langfuse.com/integrations/native/opentelemetry and update endpoint + headers accordingly.

## Disclaimer
This repository is a personal research and development project built in an individual capacity.
It is not a product offering, and it is not affiliated with, endorsed by, or representative of any employer.
