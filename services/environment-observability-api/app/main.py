from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = os.getenv("SERVICE_NAME", "environment-observability-api")
    environment: str = os.getenv("APP_ENV", "development").lower()
    version: str = os.getenv("SERVICE_VERSION", "0.1.0")
    commit_sha: str = os.getenv("GITHUB_SHA", "unknown")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    readiness_enabled: bool = os.getenv("READINESS_ENABLED", "true").lower() == "true"


settings = Settings()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "message": record.getMessage(),
            "service_name": settings.service_name,
            "service_version": settings.version,
            "environment": settings.environment,
            "commit_sha": settings.commit_sha,
        }
        for field in (
            "event_name",
            "correlation_id",
            "request_id",
            "trace_id",
            "http_method",
            "http_route",
            "http_status_code",
            "duration_ms",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["error"] = {"type": record.exc_info[0].__name__ if record.exc_info[0] else "Exception"}
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(settings.service_name)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    logger.propagate = False
    return logger


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
    trace_id = request.headers.get("traceparent", "").split("-")[1] if "-" in request.headers.get("traceparent", "") else None
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Falha não tratada na requisição",
            extra={
                "event_name": "http.request.failed",
                "correlation_id": correlation_id,
                "request_id": request_id,
                "trace_id": trace_id,
                "http_method": request.method,
                "http_route": request.url.path,
                "http_status_code": 500,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return JSONResponse(status_code=500, content={"detail": "internal_error", "correlation_id": correlation_id})

    response.headers["x-correlation-id"] = correlation_id
    response.headers["x-request-id"] = request_id
    logger.info(
        "Requisição concluída",
        extra={
            "event_name": "http.request.completed",
            "correlation_id": correlation_id,
            "request_id": request_id,
            "trace_id": trace_id,
            "http_method": request.method,
            "http_route": request.url.path,
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
            "level": settings.log_level,
            "correlation_id": True,
            "request_id": True,
            "trace_context": True,
            "sensitive_data_policy": "redact-or-hash",
        },
    }
