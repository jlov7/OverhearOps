#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from apps.service.retention import cleanup_runs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cleanup old OverhearOps run artefacts."
    )
    parser.add_argument("--base", default="runs", help="Runs directory (default: runs)")
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=168.0,
        help="Delete runs older than this age",
    )
    parser.add_argument("--keep-latest", type=int, default=200, help="Always keep newest N runs")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print cleanup results without deleting",
    )
    args = parser.parse_args()

    base = Path(args.base).resolve()
    base.mkdir(parents=True, exist_ok=True)
    removed, reclaimed_bytes = cleanup_runs(
        base=base,
        max_age_hours=max(1.0, args.max_age_hours),
        keep_latest=max(0, args.keep_latest),
        dry_run=args.dry_run,
    )
    print(
        f"cleanup_runs: removed={removed} reclaimed_bytes={reclaimed_bytes} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
