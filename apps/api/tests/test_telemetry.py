"""Regression test for OpenTelemetry pipeline-stage tracing (Phase 10 hardening)."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from proofhire_api.telemetry import traced_stage


@pytest.mark.asyncio
async def test_traced_stage_emits_a_span_with_the_given_name():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    previous_provider = trace.get_tracer_provider()
    trace.set_tracer_provider(provider)
    try:

        @traced_stage("test_stage")
        async def stage(x: int) -> int:
            return x + 1

        result = await stage(1)
    finally:
        trace.set_tracer_provider(previous_provider)

    assert result == 2
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test_stage"
