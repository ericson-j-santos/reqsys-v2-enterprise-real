"""Middleware de observabilidade enterprise — correlation_id, métricas e tracing."""

from __future__ import annotations

import time

from starlette.requests import Request
from starlette.responses import Response

from app.core.correlation import (
    definir_correlation_id,
    extrair_correlation_id_dos_headers,
    obter_correlation_id,
)
from app.core.feature_metrics import REGISTRY, identificar_feature
from app.core.otel import anotar_span_correlation
from app.core.telemetry import log_evento


async def observability_middleware(request: Request, call_next) -> Response:
    correlation_id = extrair_correlation_id_dos_headers(request.headers) or obter_correlation_id()
    definir_correlation_id(correlation_id)
    anotar_span_correlation()

    feature = identificar_feature(request.url.path)
    inicio = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - inicio) * 1000)

    REGISTRY.record(feature, response.status_code, duration_ms)
    anotar_span_correlation()

    response.headers['X-Correlation-Id'] = obter_correlation_id()
    log_evento(
        'http.request.completed',
        method=request.method,
        path=request.url.path,
        feature=feature,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response
