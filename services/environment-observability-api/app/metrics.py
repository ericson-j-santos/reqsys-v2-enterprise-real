from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

HTTP_REQUESTS_TOTAL = Counter(
    "environment_observability_http_requests_total",
    "Total de requisições HTTP processadas.",
    ("method", "route", "status_class"),
)
HTTP_ERRORS_TOTAL = Counter(
    "environment_observability_http_errors_total",
    "Total de respostas HTTP com status 4xx ou 5xx.",
    ("method", "route", "status_class"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "environment_observability_http_request_duration_seconds",
    "Duração das requisições HTTP em segundos.",
    ("method", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


def normalize_route(request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path else "unmatched"


def record_request(method: str, route: str, status_code: int, duration_seconds: float) -> None:
    status_class = f"{status_code // 100}xx"
    HTTP_REQUESTS_TOTAL.labels(method=method, route=route, status_class=status_class).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, route=route).observe(duration_seconds)
    if status_code >= 400:
        HTTP_ERRORS_TOTAL.labels(method=method, route=route, status_class=status_class).inc()


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
