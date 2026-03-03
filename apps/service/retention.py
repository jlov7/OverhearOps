from __future__ import annotations

import shutil
import time
from pathlib import Path


def run_dirs(base: Path) -> list[Path]:
    return [
        path
        for path in base.iterdir()
        if path.is_dir() and (path / "status.json").exists()
    ]


def cleanup_runs(
    base: Path,
    max_age_hours: float,
    keep_latest: int,
    dry_run: bool,
) -> tuple[int, int]:
    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    candidates = sorted(
        run_dirs(base),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    keep = set(candidates[: max(0, keep_latest)])
    removed = 0
    reclaimed_bytes = 0

    for run_dir in candidates:
        if run_dir in keep:
            continue
        mtime = run_dir.stat().st_mtime
        if mtime >= cutoff:
            continue
        size = sum(path.stat().st_size for path in run_dir.rglob("*") if path.is_file())
        if not dry_run:
            shutil.rmtree(run_dir, ignore_errors=True)
        removed += 1
        reclaimed_bytes += size
    return removed, reclaimed_bytes


__all__ = ["cleanup_runs", "run_dirs"]
