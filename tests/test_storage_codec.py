import json
from pathlib import Path

import pytest

from apps.service.storage_codec import PlainStorageCodec, resolve_storage_codec


def test_plain_storage_codec_writes_payload_and_metadata(tmp_path: Path) -> None:
    target = tmp_path / "run" / "status.json"
    codec = PlainStorageCodec(key_id="key-v1")
    codec.write_json(target, {"run_id": "r1", "status": "succeeded"})

    payload = codec.read_json(target)
    assert payload["run_id"] == "r1"
    meta_path = Path(f"{target}.meta.json")
    assert meta_path.exists()
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    assert metadata["key_id"] == "key-v1"
    assert metadata["encrypted"] is False


def test_resolve_storage_codec_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OVERHEAROPS_STORAGE_CODEC", "invalid")
    with pytest.raises(RuntimeError, match="Unsupported storage codec"):
        resolve_storage_codec()
