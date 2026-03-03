# OverhearOps Release Tracker

Last updated: 2026-03-03
Owner: Codex autonomous execution run

## Status Legend
- `DONE`: Implemented and verified in this repo.
- `IN_PROGRESS`: Actively being implemented now.
- `TODO`: Not yet implemented.
- `BLOCKED_EXTERNAL`: Requires external infra/credentials/organizational decision.

## Execution Rule
- No item is considered complete without code/tests/docs evidence in this repository.

## P0 Must-Have Release Blockers

| ID | Item | Status | Acceptance Criteria | Evidence |
|---|---|---|---|---|
| P0-01 | API auth enforcement | DONE | Protected endpoints require auth when security mode enabled | apps/service/main.py, tests/test_release_controls.py |
| P0-02 | RBAC roles (`viewer`,`operator`,`approver`,`admin`) | DONE | Route-level role checks implemented and tested | apps/service/main.py, tests/test_release_controls.py |
| P0-03 | Tenant isolation for runs/artifacts/events | DONE | Data keyed by tenant and inaccessible cross-tenant | apps/service/main.py, tests/test_release_controls.py |
| P0-04 | Secret management baseline hooks | DONE | No hard-coded secrets; env contract documented | .env.example, README.md, docs/security/secret-management.md |
| P0-05 | At-rest encryption plan and key rotation hooks | DONE | Storage abstraction allows encryption integration | apps/service/storage_codec.py, tests/test_storage_codec.py, docs/security/secret-management.md |
| P0-06 | Immutable audit log trail | DONE | Security-sensitive actions append append-only records | apps/service/main.py, runs/audit.log |
| P0-07 | Retention policy and purge path | DONE | Cleanup command purges expired runs/events | scripts/cleanup_runs.py, apps/service/retention.py, tests/test_retention_cleanup.py |
| P0-08 | DSR export/delete skeleton | DONE | API/CLI paths exist for tenant export/delete | apps/service/main.py, tests/test_release_controls.py, README.md |
| P0-09 | PII/secret redaction before persistence | DONE | Stored events/artifacts are redacted by policy | apps/service/main.py, tests/test_release_controls.py |
| P0-10 | Signed webhook/event ingestion | DONE | Optional HMAC validation for event endpoint | apps/service/main.py, tests/test_release_controls.py |
| P0-11 | Durable queue-backed execution | DONE | Jobs persist and recover across process restart | apps/service/queue_store.py, apps/service/main.py, tests/test_queue_dlq.py |
| P0-12 | Idempotency keys for run creation | DONE | Duplicate create requests return same run | apps/service/main.py, tests/test_release_controls.py |
| P0-13 | Run cancellation endpoint | DONE | `/runs/{id}/cancel` transitions running->cancelled | apps/service/main.py, tests/test_release_controls.py |
| P0-14 | Max runtime/timeout enforcement | DONE | Runs exceeding configured max are terminated/failed | apps/service/main.py, tests/test_release_controls.py |
| P0-15 | Dead-letter queue and replay tooling | DONE | Failed jobs moved to DLQ and replayable | apps/service/main.py, scripts/replay_dlq.py, tests/test_queue_dlq.py |
| P0-16 | External-call retry/circuit breaker policy | DONE | Unified policy for Graph/LLM/external calls | apps/service/adapters/teams_graph.py, packages/agentkit/provider.py, tests/test_graph_adapter_live.py, tests/test_provider_runtime.py |
| P0-17 | Strict structured-output validation with retry | DONE | Plan/judge output schema validated, failure surfaced | packages/agentkit/provider.py |
| P0-18 | Model/provider fallback routing | DONE | Failover model/provider path with policy control | packages/agentkit/provider.py, tests/test_provider_runtime.py, .env.example |
| P0-19 | Human approval gate for side effects | DONE | Non-dry-run outputs require approver role action | apps/service/main.py, tests/test_release_controls.py, README.md |
| P0-20 | Scoped integration credentials and env separation | DONE | Distinct dry-run/prod integration modes | apps/service/adapters/teams_graph.py, .env.example, README.md |
| P0-21 | SLOs and alert definitions | DONE | SLO doc + alert config templates | docs/ops/slo.md, docs/ops/alerts.yaml |
| P0-22 | Prod observability dashboard pack | DONE | Dashboard JSON/templates checked in | infra/grafana/overhearops-release-dashboard.json |
| P0-23 | Incident response runbooks | DONE | Runbooks for outage/degradation/rollback | docs/ops/incident-runbook.md |
| P0-24 | Backup/restore and DR drill doc | DONE | Reproducible backup/restore script and checklist | scripts/backup_restore.py, docs/ops/dr-backup-restore.md |
| P0-25 | Load and soak test suite | DONE | Repeatable perf test scripts + thresholds | scripts/load_soak.py, tests/perf/README.md, docs/ops/slo.md |
| P0-26 | Security CI gates (SAST/deps/secrets) | DONE | CI workflow fails on high findings | .github/workflows/security.yml |
| P0-27 | Pen-test checklist and remediation process | DONE | Documented and trackable in repo | docs/security/pentest-checklist.md |
| P0-28 | Hard release gate command | DONE | Single command enforces all required checks | scripts/release_gate.sh, Taskfile.yml |

## Release Decision (2026-03-03)
- Decision: `GO` for current release candidate.
- Basis: `P0`, `P1`, and `P2` tracker items are now implemented with repository evidence, and `./scripts/release_gate.sh` is green.
- Closure: No remaining open tracker items.

## P1 Pre-Launch Quality

| ID | Item | Status | Acceptance Criteria | Evidence |
|---|---|---|---|---|
| P1-01 | Cost/token budgets per run/tenant | DONE | Hard budgets configurable and enforced | apps/service/main.py, apps/service/runtime_config.py, apps/service/usage_meter.py, tests/test_runtime_config_and_history.py |
| P1-02 | Task-level model routing policy | DONE | plan/judge/exec routes configurable | config/runtime_settings.json, packages/agentkit/provider.py, tests/test_provider_runtime.py |
| P1-03 | Prompt version registry | DONE | Prompt versions tracked and selectable | config/prompt_registry.json, apps/service/main.py, tests/test_runtime_config_and_history.py |
| P1-04 | Canary + rollback for prompt/model changes | DONE | Automated health gate for rollout | scripts/canary_rollout.py, docs/ops/canary-rollout.md |
| P1-05 | Quality+Safety regression eval suite | DONE | Eval harness with deterministic fixture runs | tests/evals/test_regression_evals.py, docs/EVALS.md |
| P1-06 | Adversarial injection regression pack | DONE | Expanded attack suite with pass/fail output | tests/security/test_adversarial_pack.py |
| P1-07 | Run history compare/diff in UI | DONE | Compare two run IDs and show deltas | apps/ui/app/history/page.tsx, apps/ui/tests/ui.spec.ts |
| P1-08 | Search/filter/export run history | DONE | API/UI filters and export format | apps/service/main.py, apps/ui/app/history/page.tsx, tests/test_runtime_config_and_history.py |
| P1-09 | Notifications (webhook/Teams) | DONE | Completion/failure notifications configurable | apps/service/main.py, config/runtime_settings.json |
| P1-10 | Collaborative approval workflow | DONE | Multi-user approval/notes support | apps/service/main.py, tests/test_release_controls.py |
| P1-11 | Admin settings surface | DONE | Policy/env toggles visible + auditable | apps/service/main.py, apps/ui/app/admin/page.tsx, apps/ui/tests/ui.spec.ts |
| P1-12 | Feature flags + kill switches | DONE | Runtime toggles for risky integrations | apps/service/main.py, config/runtime_settings.json, tests/test_runtime_config_and_history.py |
| P1-13 | API versioning and docs completeness | DONE | Versioned route policy and docs | apps/service/main.py, docs/api-v1.md, README.md |
| P1-14 | Accessibility pass (WCAG AA) | DONE | Keyboard/screenreader checks pass | apps/ui/app/page.tsx, apps/ui/app/history/page.tsx, apps/ui/app/globals.css |
| P1-15 | Deep trace linking from UI | DONE | Jump from run page to trace/span IDs | apps/ui/app/run/[id]/page.tsx |

## P2 World-Class Differentiators

| ID | Item | Status | Acceptance Criteria | Evidence |
|---|---|---|---|---|
| P2-01 | Explainability panel with evidence chain | DONE | Winner rationale linked to observable signals | apps/ui/app/run/[id]/page.tsx |
| P2-02 | Simulation/sandbox validation mode | DONE | Dry-run simulated outcomes before apply | apps/service/main.py, tests/test_runtime_config_and_history.py |
| P2-03 | Policy-as-code governance rules | DONE | Rules loaded from versioned policy files | config/policy_rules.json, apps/service/main.py |
| P2-04 | Strategy presets (speed/safety/cost) | DONE | Runtime profile switch with measurable effects | apps/service/runtime_config.py, apps/service/main.py, apps/ui/app/admin/page.tsx |
| P2-05 | Benchmark mode + scorecards | DONE | Repeatable benchmark script outputs metrics | scripts/benchmark_scorecard.py, docs/ops/benchmark.md |
| P2-06 | Trust center docs in repo | DONE | Security architecture and controls docs | docs/security/trust-center.md |
| P2-07 | Usage metering and billing hooks | DONE | Exportable usage records by tenant | apps/service/usage_meter.py, apps/service/main.py |
| P2-08 | Product analytics funnel instrumentation | DONE | Core usage events captured and queryable | apps/service/main.py, apps/ui/lib/analytics.ts |
| P2-09 | Localization baseline | DONE | i18n-ready UI and locale-aware formatting | apps/ui/lib/i18n.ts, apps/ui/app/page.tsx, apps/ui/app/run/[id]/page.tsx |
| P2-10 | Public status checks and probes | DONE | Health probes for core paths | apps/service/main.py, scripts/probe_public_status.py |
| P2-11 | Integration health monitor jobs | DONE | Scheduled checks for Graph/Jira/provider | scripts/integration_health_check.py |
| P2-12 | Signed evidence bundles for audits | DONE | Run export bundle with hashes/signature | scripts/export_evidence_bundle.py |

## Immediate Implementation Queue (this execution pass)

1. All `P0-*` release blockers are now marked `DONE` with code/tests/docs evidence in-repo.
2. No remaining release tracker items are open.
3. Keep status evidence linked to code/tests/docs as each item lands.
