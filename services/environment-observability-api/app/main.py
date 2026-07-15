from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


LOG_SCHEMA_VERSION = "1.0"
W3C_TRACEPARENT = re.compile(
    r"^00-(?P<trace_id>[0-9a-f]{32})-(?P<span_id>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$",
    re.IGNORECASE,
)
SENSITIVE_KEY = re.compile(
    r"authorization|cookie|token|secret|password|passwd|api[_-]?key|connection[_-]?string",
    re.IGNORECASE,
)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
CPF = re.compile(r"(?<!\d)(?:\d{3}\.?){2}\d{3}-?\d{2}(?!\d)")
PHONE = re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-\s]?\d{4}(?!\d)")
BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+\-/]+=*\b")


class Settings(BaseModel):
    service_name: str = os.getenv("SERVICE_NAME", "environment-observability-api")
    environment: str = os.getenv("APP_ENV", "development").lower()
    version: str = os.getenv("SERVICE_VERSION", "0.1.0")
    commit_sha: str = os.getenv("GITHUB_SHA", "unknown")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    readiness_enabled: bool = os.getenv("READINESS_ENABLED", "true").lower() == "true"
    deployment_id: str = os.getenv("DEPLOYMENT_ID", os.getenv("FLY_IMAGE_REF", "unknown"))
    region: str = os.getenv("FLY_REGION", os.getenv("REGION", "unknown"))
    instance_id: str = os.getenv("FLY_MACHINE_ID", os.getenv("INSTANCE_ID", "unknown"))


settings = Settings()


def redact(value: Any, key: str | None = None) -> Any:
    if key and SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value

    sanitized = BEARER.sub("Bearer [REDACTED]", value)
    sanitized = EMAIL.sub("[REDACTED_EMAIL]", sanitized)
    sanitized = CPF.sub("[REDACTED_CPF]", sanitized)
    sanitized = PHONE.sub("[REDACTED_PHONE]", sanitized)
    return sanitized


def parse_traceparent(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    match = W3C_TRACEPARENT.fullmatch(value.strip())
    if not match:
        return None, None
    trace_id = match.group("trace_id").lower()
    span_id = match.group("span_id").lower()
    if trace_id == "0" * 32 or span_id == "0" * 16:
        return None, None
    return trace_id, span_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "log_schema_version": LOG_SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "message": redact(record.getMessage()),
            "service_name": settings.service_name,
            "service_version": settings.version,
            "environment": settings.environment,
            "commit_sha": settings.commit_sha,
            "deployment_id": settings.deployment_id,
            "region": settings.region,
            "instance_id": settings.instance_id,
        }
        for field in (
            "event_name",
            "event_category",
            "correlation_id",
            "request_id",
            "trace_id",
            "span_id",
            "http_method",
            "http_route",
            "http_status_code",
            "duration_ms",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = redact(value, field)
        if record.exc_info:
            payload["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            }
        return json.dumps(redact(payload), ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    service_logger = logging.getLogger(settings.service_name)
    service_logger.handlers.clear()
    service_logger.addHandler(handler)
    service_logger.setLevel(settings.log_level)
    service_logger.propagate = False
    return service_logger


logger = configure_logging()
app = FastAPI(
    title="Environment Observability API",
    version=settings.version,
    description="Serviço reutilizável para identificação de ambiente, health checks e logs estruturados.",
)


@app.middleware("http")
async def structured_access_log(request: Request, call_next):
    started = time.perf_counter()
    correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    trace_id, span_id = parse_traceparent(request.headers.get("traceparent"))
    context = {
        "event_category": "http",
        "correlation_id": correlation_id,
        "request_id": request_id,
        "trace_id": trace_id,
        "span_id": span_id,
        "http_method": request.method,
        "http_route": request.url.path,
    }
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Falha não tratada na requisição",
            extra={
                **context,
                "event_name": "http.request.failed",
                "http_status_code": 500,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "internal_error", "correlation_id": correlation_id},
        )

    response.headers["x-correlation-id"] = correlation_id
    response.headers["x-request-id"] = request_id
    logger.info(
        "Requisição concluída",
        extra={
            **context,
            "event_name": "http.request.completed",
            "http_status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )
    return response


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "healthy", "service": settings.service_name, "environment": settings.environment}


@app.get("/api/runtime/liveness")
def liveness() -> dict[str, Any]:
    return {"status": "alive"}


@app.get("/api/runtime/readiness")
def readiness() -> JSONResponse:
    ready = settings.readiness_enabled
    return JSONResponse(status_code=200 if ready else 503, content={"status": "ready" if ready else "not_ready"})


@app.get("/api/runtime/health")
def runtime_health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.version,
        "environment": settings.environment,
        "commit_sha": settings.commit_sha,
    }


@app.get("/api/v1/environment")
def environment_contract() -> dict[str, Any]:
    return {
        "service": settings.service_name,
        "environment": settings.environment,
        "version": settings.version,
        "commit_sha": settings.commit_sha,
        "logging": {
            "format": "json",
            "schema_version": LOG_SCHEMA_VERSION,
            "level": settings.log_level,
            "correlation_id": True,
            "request_id": True,
            "trace_context": "w3c",
            "redaction": True,
            "sensitive_data_policy": "redact",
        },
    }
