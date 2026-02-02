# OverhearOps — Product Requirements Document

## Problem statement
Engineering teams drown in incident chatter. Actionable signals about flaky pipelines or regressions are buried in Microsoft Teams threads, leaving release managers reacting after the damage is done. OverhearOps listens first, spots emerging incidents, assembles a just-in-time micro-team, and prepares a dry-run remediation path before the thread cools.

## Users and jobs-to-be-done
- **Engineering leads** need fast synthesis of which signals require action, a recommended branch plan, and artefacts they can delegate.
- **SRE / DevInfra engineers** need reproducible replay of the conversation, diagnostic artefacts, and confidence that agent actions stay within guardrails.
- **Product managers** want succinct impact summaries, Jira-ready mitigation notes, and governance hooks before escalation calls.

## Goals and success metrics
- **Trigger quality:** ≥85 % precision / ≥70 % recall on actionable incident-like threads during pilot.
- **Plan diversity:** ≥3 distinct remediation strategies logged per incident, with rationale and blast radius metadata.
- **Safety:** Attack success rate ≤5 % on the mini prompt-injection suite; zero blocked releases caused by agent hallucination.
- **Observability:** 100 % of runs export OpenTelemetry traces with action/component graphs rendered in the UI within five seconds.
- **Replayability:** Deterministic replay using checkpoints and offline fixtures; same seed ⇒ same artefacts and traces.

## Scope
- Ingest Teams-shaped `chatMessage` streams via NDJSON adapter.
- Durable LangGraph 1.0 execution with multi-branch execution, judge, and uncertainty gate persisted to SQLite.
- Teams-inspired UI that replays threads, inspects plan artefacts, and visualises action graphs (Adaptive Card ≤ v1.5 parity).
- Replay CLI for deterministic, event-driven re-simulation with seed control.
- Provider abstraction with offline fixtures, replay, and live mode (wire-ready).
- Safety pipeline with coordinator+guard heuristics, redaction, and attack telemetry.
- OpenTelemetry bootstrap with OTLP exporter, local collector, and Jaeger visualisation.

## Out of scope (v1)
- Production Microsoft Graph authentication, delta sync, or Teams app packaging (mocked via NDJSON).
- Autonomous code pushes, Jira creation, or Change Advisory Board integration (dry-run artefacts only).
- Voice or meeting ingestion; scope is text-based Teams chat.
- Enterprise-grade secrets rotation or HA deployments (document assumptions instead).

## Release criteria
- Single command `uv run task dev` starts backend, UI, and observability stack.
- End-to-end test covers overhear → team → plan → exec → judge → gate → ship.
- Documentation set (PRD, architecture, evals, risk register, research log) kept current in `docs/`.
- OTEL traces visible in Jaeger and mirrored in stored action-graph JSON for governance review.
- Deterministic replay proof: `uv run task replay --seed 42` reproduces previous verdict and artefacts (offline fixtures).
