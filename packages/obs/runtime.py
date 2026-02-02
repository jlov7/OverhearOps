from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class RunContext:
    run_id: str | None = None
    mode: str | None = None
    provider: str | None = None


_current: ContextVar[RunContext] = ContextVar("overhearops_run_context", default=RunContext())


def set_run_context(
    run_id: str | None,
    mode: str | None = None,
    provider: str | None = None,
) -> None:
    _current.set(RunContext(run_id=run_id, mode=mode, provider=provider))


def get_run_context() -> RunContext:
    return _current.get()
