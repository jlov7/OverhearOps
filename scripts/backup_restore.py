#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tarfile
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def backup(output: Path) -> int:
    root = _repo_root()
    targets = [
        root / "runs",
        root / "overhearops.db",
        root / "overhearops_queue.db",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as tar:
        for target in targets:
            if target.exists():
                tar.add(target, arcname=target.relative_to(root))
    print(f"Backup written: {output}")
    return 0


def restore(archive: Path) -> int:
    root = _repo_root()
    with tarfile.open(archive, "r:gz") as tar:
        resolved_root = root.resolve()
        root_prefix = f"{resolved_root}{Path('/')}"
        for member in tar.getmembers():
            target = (resolved_root / member.name).resolve()
            if not str(target).startswith(root_prefix) and target != resolved_root:
                raise ValueError(f"Archive member escapes repo root: {member.name}")
            tar.extract(member, path=resolved_root, filter="data")
    print(f"Restore completed from: {archive}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup/restore OverhearOps runtime data.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--output", required=True)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--archive", required=True)

    args = parser.parse_args()

    if args.command == "backup":
        return backup(Path(args.output).expanduser().resolve())
    return restore(Path(args.archive).expanduser().resolve())


if __name__ == "__main__":
    raise SystemExit(main())
