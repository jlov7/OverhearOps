# API v1 Surface

Base routes are available under both unversioned paths and `/api/v1/*` aliases for transition.

## Core
- `GET /api/version`
- `GET /api/v1/health`
- `GET /api/v1/threads`
- `POST /api/v1/runs`
- `GET /api/v1/runs/history`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/status`

## Extended controls
- `GET /runs/history` with filters/search.
- `GET /runs/export` (`json`/`jsonl`).
- `GET /runs/compare?left=<id>&right=<id>`.
- `POST /runs/{run_id}/simulate`.
- `POST /runs/{run_id}/approve` and `GET /runs/{run_id}/approvals`.
- `POST /runs/{run_id}/ship`.
- `GET /tenants/{tenant_id}/usage` and `GET /usage/export`.
- `GET/PUT /admin/settings`, `GET/PUT /admin/prompts`, `GET/PUT /admin/policies`.
