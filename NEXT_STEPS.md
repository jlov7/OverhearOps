# Next Steps

## 2-minute demo script
1. `uv run task dev` (ensure `npm install` in `apps/ui` and `npm install` plus `uv sync`).
2. Open `http://localhost:3000` and narrate the CI flake thread in the Teams-style column.
3. Press **Suggest Plans**; call out the three plans, the judge pick, and the uncertainty gate decision.
4. Click the run ID link to `/run/{id}` to showcase trace timeline, action/component graphs, and safety banner.
5. Optionally run `uv run task replay --seed=42` in another terminal to highlight deterministic replays and show the printed hash.

## Swap in real Microsoft Graph stream later
1. Replace `apps/service/adapters/teams_demo.py` with a Graph API client using app-only auth; preserve the `iter_messages` signature.
2. Extend `Taskfile.yml` with a `graph:sync` task that uses MSAL to fetch chat threads and writes them as NDJSON (mirrors demo loader).
3. Update environment variables (`GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`) in `.env.example` and propagate to FastAPI.
4. In the UI, read live thread IDs from a new `/api/thread` endpoint instead of the hard-coded `ci_flake` default.
5. Harden the safety pipeline with telemetry from real data (log attack detections to Grafana) before piloting with production chats.
