"""OpenTelemetry tracing setup, shared by the API and the worker.

Tracing is opt-in: with no OTEL_EXPORTER_OTLP_ENDPOINT configured, `configure_tracing`
is a no-op and `get_tracer` returns OpenTelemetry's default no-op tracer, so unit
tests and local dev without a collector are unaffected. Point the env var at a
running OTLP collector (Jaeger, Tempo, Honeycomb, Datadog, ...) to get real traces
spanning API request -> enqueue -> worker pipeline stage, tied together by the
same trace_id used in structured logs (see middleware/tracing.py).
"""

from __future__ import annotations

from functools import wraps

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured = False


def configure_tracing(service_name: str, otlp_endpoint: str) -> None:
    """Set the global TracerProvider once per process. Safe to call multiple times."""
    global _configured
    if _configured or not otlp_endpoint:
        return
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    trace.set_tracer_provider(provider)
    _configured = True


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def traced_stage(span_name: str):
    """Wrap an async pipeline-stage function in a span named `span_name`.

    A no-op (default OTel tracer) when tracing isn't configured, so this is safe
    to apply unconditionally to every worker pipeline entrypoint.
    """

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer("proofhire.pipeline")
            with tracer.start_as_current_span(span_name):
                return await fn(*args, **kwargs)

        return wrapper

    return decorator
