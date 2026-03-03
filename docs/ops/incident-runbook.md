# Incident Response Runbook

## 1. Triage
- Confirm impact: API availability, run failures, queue delays, or security event.
- Establish incident channel and incident commander.
- Capture timeframe and affected tenant(s).

## 2. Immediate Mitigation
- Disable live side effects: set `OVERHEAROPS_INTEGRATION_MODE=dry_run`.
- Pause risky traffic if needed by stopping background queue processing (`OVERHEAROPS_QUEUE_ENABLED=false`).
- Preserve evidence (`runs/`, `overhearops.db`, `overhearops_queue.db`).

## 3. Diagnose
- Inspect `/runs/dlq`, latest `runs/audit.log`, and failing run `status.json`.
- Check traces and graphs for failing spans.
- Validate external providers (OpenAI/Graph) and circuit-breaker state.

## 4. Recover
- Replay eligible failures via `POST /runs/{run_id}/replay` or `scripts/replay_dlq.py`.
- Restore from backup if data corruption is confirmed.
- Re-enable queue and live mode only after validation checks pass.

## 5. Postmortem
- Document root cause, timeline, and corrective actions.
- Add/adjust tests and release gates to prevent recurrence.
