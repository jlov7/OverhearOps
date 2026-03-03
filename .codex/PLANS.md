# OverhearOps Modernization ExecPlan

## Active Workstream (2026-03-03): Release Program Push

### Purpose / Big Picture
Drive the codebase from polished demo toward release-grade baseline by implementing the highest-impact P0 controls directly in-service, with full tracking in `.codex/RELEASE_TRACKER.md`.

### Progress
- [x] Created exhaustive tracker with 55 release items and acceptance criteria
- [x] Implement auth + RBAC scaffolding
- [x] Implement tenant-scoped run storage and lookup
- [x] Implement idempotent run creation
- [x] Implement run cancellation + timeout enforcement
- [x] Implement immutable audit trail for run lifecycle actions
- [x] Implement retention cleanup tool and tests
- [x] Implement ingest signature validation + redaction
- [x] Implement durable SQLite queue execution, DLQ listing, and replay endpoint/script with tests
- [x] Implement OpenAI fallback model + circuit breaker tests and shared external retry/circuit policy
- [x] Implement approval-gated live shipping and integration credential scoping (dry-run/prod)
- [x] Implement DSR export/delete skeleton endpoints with admin-role guard and tests
- [x] Implement storage codec abstraction with key-rotation metadata hooks and tests
- [x] Add release ops pack: SLOs, alerts, dashboard template, incident runbook, DR backup/restore docs + scripts
- [x] Add security CI workflow (SAST/dependency/secret scans) and pen-test checklist
- [x] Add hard release gate script/task and verify it passes
- [x] Review and formally close remaining backlog items as explicit post-launch deferrals
- [x] Full gate verification and status refresh

### Decision Log
- Decision: Execute a concrete P0 tranche now instead of waiting for full multi-week roadmap.
  Reason: Immediate measurable risk reduction and continuous release hardening.
- Decision: Keep new security controls configurable so offline demo flows remain runnable.
  Reason: Preserve local developer velocity while enabling production behavior by env.

## Purpose / Big Picture
Raise OverhearOps from polished demo to a more production-credible, frontier-aligned baseline by eliminating current reliability failures, hardening critical runtime seams, and improving verification quality. The immediate objective is a fully green local gate set with safer defaults and better observability/test confidence.

## Progress
- [x] Baseline stabilized: lint + typecheck + build + tests all green
- [x] Runtime hardening completed and regression-tested
- [x] UI build/runtime reliability improvements completed
- [x] E2E tests upgraded from static markup checks to application-flow validation
- [x] Final verification evidence collected and summarized
- [x] Added run lifecycle endpoints (`/runs`, `/runs/{id}/status`) with background execution support
- [x] Added provider resolver with OpenAI Responses-compatible live path and env-driven config
- [x] Added bounded thread event ingestion guard (`OVERHEAROPS_MAX_THREAD_EVENTS`)

## Surprises & Discoveries
- `pytest` passed while `ruff` and `mypy` failed, indicating uneven quality gate enforcement.
- UI production build fails due to missing `clsx` dependency even though lint passes.
- Existing Playwright test is synthetic (`setContent`) and does not validate real app behavior.
- Determinism was partially broken by dynamic Jira timestamps; fixed by mode-aware deterministic artefact timestamping in offline/replay.
- Running `next build` and Playwright (with dev server) in parallel can race on build artifacts; sequential verification is stable.

## Decision Log
- Decision: Fix gating failures first before larger architectural changes.
  Reason: Prevent hidden regressions and establish reliable baseline.
- Decision: Keep adapter/LLM default modes backward compatible (offline demo first).
  Reason: Preserve existing demo behavior while improving seams.
- Decision: Prefer targeted high-impact hardening over broad speculative refactors.
  Reason: Minimize risk and align with anti-over-engineering constraints.

## Files To Modify (initial target set)
- `apps/service/main.py`
- `packages/agentkit/graph.py`
- `packages/agentkit/judge.py`
- `packages/obs/runtime.py`
- `packages/obs/exporter_file.py`
- `apps/ui/package.json`
- `apps/ui/tests/ui.spec.ts`
- `apps/ui/playwright.config.ts` (if needed for real-flow E2E)

## Risks
- Dependency upgrades may introduce API shifts; keep upgrades incremental and verified.
- Real-flow Playwright tests may require explicit test server orchestration.
- Security tightening (e.g., CORS) must remain configurable for local demo UX.

## Validation Gates
- `uv run ruff check .`
- `uv run mypy .`
- `uv run pytest -q`
- `npm run --prefix apps/ui lint`
- `npm run --prefix apps/ui build`
- `npm run --prefix apps/ui test`

## Outcomes & Retrospective
- Completed a full green pass across all configured gates.
- Improved runtime defaults/security posture without changing offline-first demo semantics.
- Increased UI confidence by validating a real app route with mocked API payloads instead of static HTML assertions.
- Expanded backend lifecycle capabilities so runs are now queueable/pollable for long-running workflows.
- Added live-provider architecture while keeping deterministic fixture parity for offline/replay.
- Closed the full P0 release-blocker set in `.codex/RELEASE_TRACKER.md` with code/tests/docs evidence.
- Added release-readiness closure decision (`GO`) and explicit `DEFERRED` status for non-blocking P1/P2 backlog.
