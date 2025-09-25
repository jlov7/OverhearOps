# OverhearOps — Evaluations

## Metrics
- **Trigger precision/recall:** Compare overhear intent predictions with hand-labelled Teams threads; target ≥85 % precision / ≥70 % recall.
- **Plan diversity:** Count distinct mitigation branches per run; alert if <3 unique hypotheses logged.
- **Judge alignment:** Measure agreement between multi-agent judge decision and human reviewer verdicts (≥80 %).
- **Artefact completeness:** Ensure dry-run PR diff, Jira payload, and runbook note reference the winning plan and include blast-radius context.
- **Safety resilience:** Track attack success rate on the 8x5 prompt-injection mini-suite (target ASR = 0) and capture guard categories.
- **Span graph coverage & invocation correctness:** Ensure span-derived action graphs include ≥7 nodes with linear chain across overhear→ship and parent→child edges match the LangGraph execution order.
- **Replay determinism:** Hash ordered OTEL spans and artefact metadata; drift triggers regression investigation.

## Test surfaces
- **Unit:** Intent detection heuristics, team composition diversity scoring, planner branch generator, executor artefact and guard logic, judge/uncertainty logic, defence classifier redaction.
- **Integration:** FastAPI `POST /run/{thread}` ⇒ LangGraph pipeline ⇒ stored artefacts, spans, graphs, and replay hash.
- **UI:** Smoke test main page, run detail view, action graph panel (Playwright optional).
- **Observability:** OTEL exporter configuration fallback, Jaeger collector connectivity, span-to-graph conversion stub.

## Automation
- `task lint` ⇒ Ruff + mypy; `task test` ⇒ pytest suite (unit, safety attack suite, replay hash, API smoke) with optional Playwright toggle.
- Replay harness (`task replay --seed 42`) baked into CI to assert deterministic artefacts and hash stability.
- Safety suite iterates ATTACK_SUITE prompts and reports ASR; governance modal surfaces pass/fail state.

## Reporting
- Persist evaluation metadata in `runs/{run_id}/artefacts.json` and future governance modal.
- Jaeger dashboards provide span timelines; extend with Grafana once OTEL metrics enabled.
- Document evaluation cadence (weekly) in README and capture regression notes in `docs/EVALS.md` appendices when available.
