# OverhearOps Release Notes — 2026-03-03

## Release Summary
This release moves OverhearOps from a demo-grade prototype to a release-ready candidate with hardened runtime controls, stronger governance, expanded operator UX, and a complete verification gate.

## Major Additions
- Runtime configuration system for feature flags, strategy presets, model routing, budgets, and policy rules.
- Durable queue execution with DLQ handling, replay tooling, run cancellation, and timeout enforcement.
- Security and governance controls: auth/RBAC, tenant isolation, approval quorum, audit trail, retention cleanup, DSR export/delete skeleton, redaction, signed ingest.
- Reliability hardening: provider fallback, external retry/circuit policy, strict output validation paths.
- New API capabilities: run history/export/compare, simulation endpoint, admin settings/prompt/policy APIs, health/public status probes, usage export.
- UI expansion: history compare/export page, admin controls page, enhanced run detail explainability/trace linking, accessibility improvements, i18n baseline, analytics hooks.
- Ops and release tooling: release gate, canary rollout script, benchmark scorecard script, integration health checks, signed evidence bundle export.
- Documentation pack for architecture, API v1, evals, SLO/alerts, incident response, DR, trust center, and security checklists.

## Verification Evidence
- `./scripts/release_gate.sh` passes end-to-end.
- Python gates: `ruff`, `mypy`, `pytest` all green (`71 passed`).
- UI gates: `next lint`, `next build`, `playwright test` all green (`3 passed`).
- Release tracker confirms P0/P1/P2 closure with repository evidence links.

## Known Remaining Work
- No open release tracker items for this release candidate.

## Operator Notes
- Use `/admin` for runtime settings, prompt registry, policies, and strategy presets.
- Use `/history` for run search, export, and compare workflows.
- Use `/run/{id}` for explainability and trace-linked diagnostics.
