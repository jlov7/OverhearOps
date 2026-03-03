# OverhearOps Trust Center

## Security Controls
- API authentication and RBAC (`viewer`, `operator`, `approver`, `admin`).
- Tenant isolation in run history, artefacts, approvals, usage, and DSR endpoints.
- Signed webhook ingest option (`X-OverhearOps-Signature`).
- Redaction pipeline for sensitive text before persistence.
- Immutable audit records (`runs/audit.log` + per-run audit logs).

## Data Governance
- DSR skeleton endpoints: export and delete by tenant.
- Retention cleanup script for aging run data.
- Storage codec abstraction with key-rotation metadata hooks.

## Reliability
- Queue-backed background execution and stale-lease requeue.
- Timeout and cancellation handling.
- DLQ with replay tooling.
- External call retry + circuit breaker policies.

## Operational Readiness
- SLO and alert templates.
- Incident response runbook.
- Backup/restore and DR drill guide.
- Release gate command and CI security workflow.
