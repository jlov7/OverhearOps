from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ProviderConfig:
    mode: str
    provider: str
    base_dir: str | None = None


class LLMProvider:
    def generate_json(
        self,
        task: str,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        raise NotImplementedError


class OfflineProvider(LLMProvider):
    def __init__(self, base_dir: str = "data/demo/llm") -> None:
        self.base_dir = Path(base_dir)

    def generate_json(
        self,
        task: str,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        path = self.base_dir / thread_id / f"{task}.json"
        return json.loads(path.read_text(encoding="utf-8"))
