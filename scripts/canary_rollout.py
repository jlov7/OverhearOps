#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "config" / "runtime_settings.json"
PROMPTS = ROOT / "config" / "prompt_registry.json"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Canary rollout and rollback for prompt/model config."
    )
    parser.add_argument("--candidate-settings", help="Path to candidate runtime_settings.json")
    parser.add_argument("--candidate-prompts", help="Path to candidate prompt_registry.json")
    args = parser.parse_args()

    backup_settings = SETTINGS.with_suffix(".json.bak")
    backup_prompts = PROMPTS.with_suffix(".json.bak")
    shutil.copy2(SETTINGS, backup_settings)
    shutil.copy2(PROMPTS, backup_prompts)

    try:
        if args.candidate_settings:
            shutil.copy2(Path(args.candidate_settings).expanduser().resolve(), SETTINGS)
        if args.candidate_prompts:
            shutil.copy2(Path(args.candidate_prompts).expanduser().resolve(), PROMPTS)

        result = _run(["uv", "run", "pytest", "-q", "tests/evals", "tests/security"])
        print(result.stdout)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Canary evals failed.")
        print("Canary rollout succeeded.")
        return 0
    except Exception as exc:  # noqa: BLE001
        shutil.copy2(backup_settings, SETTINGS)
        shutil.copy2(backup_prompts, PROMPTS)
        print(f"Canary failed, rollback applied: {exc}")
        return 1
    finally:
        if backup_settings.exists():
            backup_settings.unlink()
        if backup_prompts.exists():
            backup_prompts.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
