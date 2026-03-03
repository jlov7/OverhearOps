# Performance Suite

Use the load/soak harness:

```bash
uv run python scripts/load_soak.py --base-url http://localhost:8000 --concurrency 20 --requests-per-worker 50
```

Capture results for release gates and compare against SLO targets in `docs/ops/slo.md`.
