# OverhearOps — Risk Register

| Risk | Description | Impact | Mitigation |
| --- | --- | --- | --- |
| False positives | Agent escalates benign chatter, wasting attention and trust. | Medium | Raise intent threshold, expose manual override in UI, feed reviewer feedback into heuristics. |
| Prompt injection | Malicious users coerce tools or leak secrets via Teams thread. | High | Coordinator+Guard pipeline, redact outputs, log all defences, expand attack suite (8×5 variants). |
| Model drift | Intent or judge heuristics degrade as incidents evolve. | Medium | Weekly replay against regression threads, monitor precision/recall in dashboards, refresh heuristics. |
| Observability gaps | Missing OTEL spans break action-graph reconstruction. | Medium | Fail fast on exporter misconfig, keep Jaeger docker-compose in `task dev`, add tests for exporter initialisation. |
| Determinism regressions | Replay with same seed produces different artefacts. | Medium | Hash run outputs, add regression test in CI, surface drift in governance modal. |
| Cost / latency | Multi-branch planning increases runtime and token spend. | Low | Cap branch width via `OVERHEAROPS_BRANCH_WIDTH`, cache heuristics, fall back to abstain on budget breach. |
| Compliance | Real tenant data requires retention, DSR, and audit trails. | High | Keep demo data synthetic, document data handling TODO before production adapter, enforce env-var secrets discipline. |
