"""OpenTelemetry setup for the Voco Cognitive Engine.

Provides a configurable TracerProvider:
  - **dev** (default): ConsoleSpanExporter — spans print to stdout.
  - **prod**: OTLPSpanExporter — ships spans to an OTLP-compatible collector.

Usage:
    from src.telemetry import init_telemetry, get_tracer

    init_telemetry()          # call once at startup (lifespan)
    tracer = get_tracer()     # use anywhere
    with tracer.start_as_current_span("my.span"):
        ...
"""

from __future__ import annotations

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

logger = logging.getLogger(__name__)

_SERVICE_NAME = "voco-cognitive-engine"
_TRACER_NAME = "voco"
_initialized = False


def init_telemetry() -> None:
    """Initialise the global TracerProvider.

    Reads ``OTEL_EXPORTER`` from the environment:
      - ``"otlp"`` → OTLPSpanExporter (requires ``OTEL_EXPORTER_OTLP_ENDPOINT``)
      - anything else → ConsoleSpanExporter (default for local dev)
    """
    global _initialized
    if _initialized:
        return

    resource = Resource.create({"service.name": _SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    exporter_type = os.environ.get("OTEL_EXPORTER", "console").lower()
    if exporter_type == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            logger.info("[Telemetry] OTLP exporter → %s", endpoint)
        except ImportError:
            logger.warning("[Telemetry] OTLP exporter not installed — falling back to console.")
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        logger.info("[Telemetry] Console exporter active (dev mode).")

    trace.set_tracer_provider(provider)
    _initialized = True


def get_tracer() -> trace.Tracer:
    """Return the Voco tracer (safe to call before ``init_telemetry``)."""
    return trace.get_tracer(_TRACER_NAME)


def current_trace_id() -> str:
    """Return the hex trace-id of the current span, or empty string if none."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.trace_id:
        return format(ctx.trace_id, "032x")
    return ""
