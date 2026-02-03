# OverhearOps Demo Hardening Design

**Date:** 2026-02-03

## Goal
Perfect the demo with a second scenario, deterministic replay checks, and clear UI signals, while keeping changes low risk and fully offline by default.

## Scope
- Add a second demo thread (security scenario) with full offline fixtures.
- Strengthen determinism testing (artefacts + replay hash stable across runs).
- Run demo smoke and update docs to reflect multi-scenario demo.
- Apply safe, non-breaking dependency updates (no forced audit fixes).
- Minimal UI polish: Mode/Provider badge, plans executed counter, and clearer winner context.

## Non-Goals
- Major UI redesign
- Live LLM integration
- Production Graph adapter

## Data Flow Updates
1. New security thread is stored as NDJSON in `data/demo/threads`.
2. Offline fixtures for planning/judging live in `data/demo/llm/security`.
3. Thread list endpoint exposes both threads; UI thread selector defaults to available threads.
4. Run payload includes mode/provider and per-plan artefacts for auditable display.

## Determinism
- Add a test that runs the same thread twice in offline mode and compares:
  - `artefacts_by_plan` equality
  - `replay_hash` equality
- This test is part of pytest and runs without OTEL collector.

## Dependency Policy
- Run `npm audit fix` only without `--force`.
- Upgrade patch/minor versions within the same major version.
- Defer breaking upgrades to a separate, intentional pass.

## UI Adjustments
- Show Mode/Provider badge on run page.
- Display “Plans executed” counter.
- Retain existing plan cards but highlight the winner clearly.
- Add brief safety summary near gate state.

## Documentation
- Update demo deck to mention multiple scenarios and offline determinism.
- Update evals and PRD to reference the new security scenario and determinism test.

## Success Criteria
- Two demo scenarios run end-to-end offline.
- Determinism test passes.
- Frontend tests pass.
- Demo flow is clearer (provider/mode/gate/plan count visible).
