# Benchmark Mode + Scorecard

Generate a scorecard from load + eval suites:

```bash
uv run python scripts/benchmark_scorecard.py --output docs/ops/benchmark-scorecard.json
```

The scorecard includes:
- Load/soak command exit status and output.
- Eval/security suite exit status and output.
- Aggregate pass/fail result.
