import os
import time
from pathlib import Path

from apps.service.retention import cleanup_runs


def _make_run(base: Path, name: str, age_s: int) -> Path:
    run = base / name
    run.mkdir(parents=True, exist_ok=True)
    (run / "status.json").write_text("{}", encoding="utf-8")
    (run / "artefacts.json").write_text("{}", encoding="utf-8")
    ts = time.time() - age_s
    os.utime(run, (ts, ts))
    return run


def test_cleanup_runs_respects_age_and_keep_latest(tmp_path: Path) -> None:
    base = tmp_path / "runs"
    base.mkdir(parents=True, exist_ok=True)

    newest = _make_run(base, "newest", age_s=60)
    _make_run(base, "old-1", age_s=60 * 60 * 24 * 10)
    _make_run(base, "old-2", age_s=60 * 60 * 24 * 12)

    removed, _ = cleanup_runs(
        base=base,
        max_age_hours=24,
        keep_latest=1,
        dry_run=False,
    )
    assert removed == 2
    assert newest.exists()


def test_cleanup_runs_dry_run_does_not_delete(tmp_path: Path) -> None:
    base = tmp_path / "runs"
    base.mkdir(parents=True, exist_ok=True)
    stale = _make_run(base, "stale", age_s=60 * 60 * 24 * 20)

    removed, _ = cleanup_runs(
        base=base,
        max_age_hours=24,
        keep_latest=0,
        dry_run=True,
    )
    assert removed == 1
    assert stale.exists()
