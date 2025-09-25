"""File-based span exporter for demo replay capture."""

from __future__ import annotations

import json
import os
from pathlib import Path

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


class FileSpanExporter(SpanExporter):
    """Append spans for the active run to `runs/{id}/spans.jsonl`."""

    def export(self, spans):  # type: ignore[override]
        run_id = os.getenv("OVERHEAROPS_RUN_ID")
        if not run_id:
            return SpanExportResult.SUCCESS
        base = Path(__file__).resolve().parents[2] / "runs" / run_id
        base.mkdir(parents=True, exist_ok=True)
        out = base / "spans.jsonl"
        with out.open("a", encoding="utf-8") as handle:
            for span in spans:
                handle.write(
                    json.dumps(
                        {
                            "span_id": span.context.span_id,
                            "trace_id": span.context.trace_id,
                            "name": span.name,
                            "start_time": span.start_time,
                            "end_time": span.end_time,
                            "parent_id": span.parent.span_id if span.parent else None,
                            "attributes": dict(span.attributes or {}),
                        }
                    )
                    + "\n"
                )
        return SpanExportResult.SUCCESS


__all__ = ["FileSpanExporter"]
