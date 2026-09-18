from __future__ import annotations

import os


def _enabled() -> bool:
    return os.getenv("OTEL_TRACING_ENABLED", "false").lower() == "true"


def configure_opentelemetry() -> bool:
    if not _enabled():
        return False

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if not endpoint:
        return False

    resource = Resource.create(
        {
            "service.name": os.getenv("SERVICE_NAME", "environment-observability-api"),
            "service.version": os.getenv("SERVICE_VERSION", "0.1.0"),
            "deployment.environment.name": os.getenv("APP_ENV", "development"),
            "service.instance.id": os.getenv("FLY_MACHINE_ID", os.getenv("INSTANCE_ID", "unknown")),
            "cloud.region": os.getenv("FLY_REGION", os.getenv("REGION", "unknown")),
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, timeout=5)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor().instrument(
        excluded_urls="/health,/api/runtime/liveness,/api/runtime/readiness,/metrics"
    )
    return True


try:
    OTEL_CONFIGURED = configure_opentelemetry()
except Exception:
    # Telemetria nunca deve impedir a inicialização do serviço.
    OTEL_CONFIGURED = False
