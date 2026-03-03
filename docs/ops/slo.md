# OverhearOps SLOs

## Service-Level Objectives (30-day)
- API availability: 99.9% for `/health`, `/runs`, `/runs/{id}/status`.
- Run completion success: >= 99.0% for non-cancelled runs.
- P95 run completion time: <= 180s for demo workloads.
- Queue recovery: stale running jobs requeued within 2 lease intervals.

## Error Budgets
- Availability budget: 43.2 minutes/month.
- Run success budget: 1% failed (excluding cancel requests).

## Burn Alerts
- Fast burn: >10% budget burn in 1 hour.
- Slow burn: >5% budget burn in 6 hours.

## Operational Owner
- Primary: release engineering on-call.
- Secondary: platform/runtime owner.
