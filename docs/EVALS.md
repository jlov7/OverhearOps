# OverhearOps — Evaluations

## Metrics
- **Trigger precision/recall:** Compare overhear intent predictions with hand-labelled Teams threads; target ≥85 % precision / ≥70 % recall.
- **Plan diversity:** Count distinct mitigation branches per run; alert if <3 unique hypotheses logged.
- **Judge alignment:** Measure agreement between multi-agent judge decision and human reviewer verdicts (≥80 %).
- **Artefact completeness:** Ensure dry-run PR diff, Jira payload, and runbook note reference the winning plan and include blast-radius context.
- **Safety resilience:** Track attack success rate on 8×5 prompt-injection mini-suite (≤5 %) and log redaction coverage.
- **Replay determinism:** Hash ordered OTEL spans + artefact JSON; drift triggers regression investigation.

## Test surfaces
- **Unit:** Intent detection heuristics, team composition diversity scoring, planner branch generator, executor artefact render, judge/uncertainty logic, defence pipeline redaction.
- **Integration:** FastAPI `POST /run/{thread}` ⇒ LangGraph pipeline ⇒ stored artefacts and action graph JSON.
- **UI:** Smoke test main page, run detail view, action graph panel (Playwright optional).
- **Observability:** OTEL exporter configuration fallback, Jaeger collector connectivity, span-to-graph conversion stub.

## Automation
- `task lint` ⇒ Ruff + mypy; `task test` ⇒ pytest suite (unit + API smoke) with optional Playwright toggle.
- Replay harness (`task replay --seed 42`) baked into CI to assert deterministic artefacts.
- Safety suite iterates ATTACK_SUITE prompts and reports ASR; integrates with governance dashboard.

## Reporting
- Persist evaluation metadata in `runs/{run_id}/artefacts.json` and future governance modal.
- Jaeger dashboards provide span timelines; extend with Grafana once OTEL metrics enabled.
- Document evaluation cadence (weekly) in README and capture regression notes in `docs/EVALS.md` appendices when available.
