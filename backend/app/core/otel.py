"""Bootstrap OpenTelemetry — opt-in via OTEL_ENABLED."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.config import settings
from app.core.correlation import obter_correlation_id

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger('reqsys.otel')
_otel_configured = False
_http_request_counter: Any | None = None
_http_duration_histogram: Any | None = None


def otel_ativo() -> bool:
    return _otel_configured


def _signal_endpoint(base_endpoint: str, signal: str) -> str:
    """Normaliza endpoint OTLP/HTTP para /v1/{signal}."""
    base = (base_endpoint or '').strip().rstrip('/')
    for suffix in ('/v1/traces', '/v1/metrics', '/v1/logs'):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return f'{base}/v1/{signal}' if base else ''


def configurar_opentelemetry(app: FastAPI) -> bool:
    global _otel_configured, _http_request_counter, _http_duration_histogram
    if not settings.otel_enabled:
        return False
    if _otel_configured:
        return True

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            ConsoleMetricExporter,
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError:
        logger.warning('OpenTelemetry habilitado mas pacotes nao instalados — telemetria desativada')
        return False

    resource = Resource.create(
        {
            'service.name': settings.otel_service_name,
            'service.version': settings.app_version,
            'deployment.environment': settings.normalized_environment,
        }
    )
    tracer_provider = TracerProvider(resource=resource)

    if settings.otel_exporter_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                OTLPMetricExporter,
            )
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            trace_exporter = OTLPSpanExporter(
                endpoint=_signal_endpoint(settings.otel_exporter_endpoint, 'traces')
            )
            metric_exporter = OTLPMetricExporter(
                endpoint=_signal_endpoint(settings.otel_exporter_endpoint, 'metrics')
            )
        except ImportError:
            logger.warning('OTLP exporter indisponivel — usando console exporters')
            trace_exporter = ConsoleSpanExporter()
            metric_exporter = ConsoleMetricExporter()
    else:
        trace_exporter = ConsoleSpanExporter()
        metric_exporter = ConsoleMetricExporter()

    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=60_000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    meter = meter_provider.get_meter('reqsys.runtime', version=settings.app_version)

    _http_request_counter = meter.create_counter(
        'reqsys.http.server.requests',
        unit='{request}',
        description='Quantidade de requests HTTP processadas pelo ReqSys.',
    )
    _http_duration_histogram = meter.create_histogram(
        'reqsys.http.server.duration',
        unit='ms',
        description='Distribuição de duração das requests HTTP do ReqSys.',
    )

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls='/health,/api/runtime/liveness',
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )
    HTTPXClientInstrumentor().instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    _otel_configured = True
    logger.info(
        'opentelemetry_configurado service=%s traces=%s metrics=%s',
        settings.otel_service_name,
        _signal_endpoint(settings.otel_exporter_endpoint, 'traces') or 'console',
        _signal_endpoint(settings.otel_exporter_endpoint, 'metrics') or 'console',
    )
    return True


def registrar_http_metricas(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """Registra métricas HTTP de baixa cardinalidade no MeterProvider configurado."""
    if not _otel_configured or _http_request_counter is None or _http_duration_histogram is None:
        return

    attributes = {
        'http.request.method': method.upper(),
        'http.route': route or 'unknown',
        'http.response.status_code': int(status_code),
    }
    try:
        _http_request_counter.add(1, attributes)
        _http_duration_histogram.record(max(0.0, float(duration_ms)), attributes)
    except Exception:
        logger.exception('otel_http_metrics_record_failed')


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
