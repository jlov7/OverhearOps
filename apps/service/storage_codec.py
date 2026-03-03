from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol, cast


class StorageCodec(Protocol):
    def write_json(self, path: Path, payload: dict[str, Any]) -> None: ...

    def read_json(self, path: Path) -> dict[str, Any]: ...


class PlainStorageCodec:
    def __init__(self, key_id: str = "") -> None:
        self.key_id = key_id.strip()

    @staticmethod
    def _meta_path(path: Path) -> Path:
        return Path(f"{path}.meta.json")

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, sort_keys=True, default=str),
            encoding="utf-8",
        )
        if self.key_id:
            metadata = {
                "codec": "plain",
                "encrypted": False,
                "key_id": self.key_id,
            }
            self._meta_path(path).write_text(
                json.dumps(metadata, sort_keys=True, default=str),
                encoding="utf-8",
            )

    def read_json(self, path: Path) -> dict[str, Any]:
        payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        return payload


def resolve_storage_codec() -> StorageCodec:
    codec_name = os.getenv("OVERHEAROPS_STORAGE_CODEC", "plain").strip().lower()
    key_id = os.getenv("OVERHEAROPS_STORAGE_KEY_ID", "")
    if codec_name == "plain":
        return PlainStorageCodec(key_id=key_id)
    raise RuntimeError(
        f"Unsupported storage codec '{codec_name}'. "
        "Set OVERHEAROPS_STORAGE_CODEC=plain or install a custom codec."
    )


__all__ = ["StorageCodec", "resolve_storage_codec"]
