#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(  # noqa: S603
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark mode and scorecard generator.")
    parser.add_argument("--output", default="docs/ops/benchmark-scorecard.json")
    args = parser.parse_args()

    started = int(time.time() * 1000)
    perf_code, perf_out, perf_err = _run(
        [
            "uv",
            "run",
            "python",
            "scripts/load_soak.py",
            "--base-url",
            "http://localhost:8000",
            "--concurrency",
            "10",
            "--requests-per-worker",
            "20",
        ]
    )
    eval_code, eval_out, eval_err = _run(
        ["uv", "run", "pytest", "-q", "tests/evals", "tests/security"]
    )

    scorecard = {
        "generated_at_ms": started,
        "perf": {
            "exit_code": perf_code,
            "stdout": perf_out.strip(),
            "stderr": perf_err.strip(),
        },
        "evals": {
            "exit_code": eval_code,
            "stdout": eval_out.strip(),
            "stderr": eval_err.strip(),
        },
        "overall_pass": perf_code == 0 and eval_code == 0,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scorecard, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote scorecard: {output}")
    return 0 if scorecard["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
