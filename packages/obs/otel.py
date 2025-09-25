import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

from packages.obs.exporter_file import FileSpanExporter


def init_otel(service_name: str):
    provider = TracerProvider()
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    header_str = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
    headers = None
    if header_str:
        pairs = [item.strip() for item in header_str.split(",") if "=" in item]
        headers = {
            key.strip(): value.strip()
            for key, value in (pair.split("=", 1) for pair in pairs)
        }
    otlp_exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", headers=headers)
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    # Chain OTLP and file exporters per OpenTelemetry Python exporter guidance.
    provider.add_span_processor(SimpleSpanProcessor(FileSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)
