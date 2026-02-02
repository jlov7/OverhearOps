# OverhearOps Demo Excellence Design

**Date:** 2026-02-02

## Goal
Deliver a zero-cost, reliable demo that feels production-grade: real multi-branch reasoning, strong governance, deterministic replay, and a ready-to-wire LLM provider layer with offline fallback.

## Audience
- Engineering leadership / SREs (technical credibility)
- Prospective customers / partners (workflow trust + enterprise fit)
- Conference/talk attendees (clear narrative + visible observability)

## Non-Goals
- Production Microsoft Graph ingestion (adapter remains stubbed)
- Real writes (PR/Jira) beyond dry-run artifacts
- Enterprise security/compliance hardening beyond demo-grade guardrails

## Product Narrative
OverhearOps listens to Teams-style threads, detects actionable intent, assembles a micro-team, explores 2-3 plans, judges a winner, and ships only when safe. Every decision is traced, replayable, and auditable.

## Architecture Updates (High Level)
- True multi-branch execution: exec runs per plan branch, artefacts stored by plan_id.
- Judge selects a winner from executed branches; gate enforces ship/abstain.
- Ship returns winning artefacts only when approved; otherwise returns blocked summary.
- Provider abstraction supports offline + record/replay + live provider modes.

## LLM Provider Modes
- **offline:** deterministic fixtures; zero cost; fully replayable.
- **record:** live provider + store responses per node/plan_id.
- **replay:** use stored responses for deterministic playback.
- **live:** direct provider calls with tracing and caching.

## Data Model (Run Payload)
A single payload shape is shared by API, UI, and disk:
- run_id, thread_id, mode, provider
- plans[]
- branches[] (plan_id + artefact refs)
- artefacts_by_plan[plan_id]
- verdict { winner_plan_id, rationale, votes[] }
- gate { action, certainty }
- safety_summary { allowed, categories }
- replay_hash
- graphs { action_graph, component_graph }
- metadata { seed, timestamps, branch_width }

## API Surface
- GET /threads -> list demo threads
- GET /threads/{id} -> thread messages
- POST /run/{id} -> execute pipeline
- GET /runs/{run_id} -> run payload
- GET /runs/{run_id}/graphs.json -> graphs snapshot
- POST /threads/{id}/events -> optional replay stream

## Replay and Determinism
- Run IDs include high-entropy suffix (timestamp + random token).
- File span exporter uses a per-run context token (no global env collisions).
- Replay hashes cover ordered spans + artefacts metadata.

## Demo UI Updates
- Thread list + selected thread
- Plan cards for all branches
- Judge panel: votes, winner, rationale
- Gate panel: approve/abstain + certainty
- Governance modal: trace IDs, replay hash, provider/mode, reproduce command

## Safety
- Guard at three points: raw thread, plan text, artefacts
- No ship when blocked or abstain
- Safety decisions stored per plan and rolled up into a summary

## Evaluation
- Offline deterministic tests for:
  - multi-branch execution correctness
  - gate enforcement and safety blocking
  - replay hash stability
  - API payload shape
  - UI smoke tests (thread, plans, governance)

## Success Criteria
- Demo runs offline with deterministic output and zero cost.
- Multi-branch execution produces artefacts per plan.
- Gate blocks shipping when confidence is low or safety fails.
- UI reflects all branches, vote counts, and gate decision.
- Replay command reproduces the same hash and artefacts.

## Milestones
1) Provider abstraction + offline fixtures
2) Multi-branch execution + gate enforcement
3) API surface normalization
4) UI refresh for branch/judge/gate
5) Determinism tests + documentation updates
