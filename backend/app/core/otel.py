"""Bootstrap OpenTelemetry — opt-in via OTEL_ENABLED."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.correlation import obter_correlation_id

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger('reqsys.otel')
_otel_configured = False


def otel_ativo() -> bool:
    return _otel_configured


def configurar_opentelemetry(app: FastAPI) -> bool:
    global _otel_configured
    if not settings.otel_enabled:
        return False
    if _otel_configured:
        return True

    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError:
        logger.warning('OpenTelemetry habilitado mas pacotes nao instalados — tracing desativado')
        return False

    resource = Resource.create(
        {
            'service.name': settings.otel_service_name,
            'service.version': settings.app_version,
            'deployment.environment': settings.normalized_environment,
        }
    )
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
        except ImportError:
            logger.warning('OTLP exporter indisponivel — usando console exporter')
            exporter = ConsoleSpanExporter()
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls='/health,/api/runtime/liveness')
    HTTPXClientInstrumentor().instrument()

    _otel_configured = True
    logger.info(
        'opentelemetry_configurado service=%s exporter=%s',
        settings.otel_service_name,
        settings.otel_exporter_endpoint or 'console',
    )
    return True


def anotar_span_correlation() -> None:
    if not _otel_configured:
        return
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute('reqsys.correlation_id', obter_correlation_id())
    except Exception:
        return
