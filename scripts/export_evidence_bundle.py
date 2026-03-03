#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export signed evidence bundle for a run.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", default="runs/evidence")
    parser.add_argument("--secret", default=os.getenv("OVERHEAROPS_EVIDENCE_SIGNING_SECRET", ""))
    args = parser.parse_args()

    run_dir = RUNS / args.run_id
    if not run_dir.exists():
        raise SystemExit("Run not found")

    out_dir = (ROOT / args.output).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{args.run_id}.tar.gz"

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(run_dir, arcname=args.run_id)

    manifest = {
        "run_id": args.run_id,
        "archive": str(archive),
        "archive_sha256": _hash_file(archive),
        "files": [],
    }
    for file_path in sorted(run_dir.rglob("*")):
        if file_path.is_file():
            manifest["files"].append(
                {
                    "path": str(file_path.relative_to(ROOT)),
                    "sha256": _hash_file(file_path),
                }
            )

    payload = json.dumps(manifest, sort_keys=True).encode("utf-8")
    signature = ""
    if args.secret:
        signature = hmac.new(args.secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    manifest["signature"] = signature
    manifest_path = out_dir / f"{args.run_id}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({"archive": str(archive), "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
