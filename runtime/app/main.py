from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api import jobs
from app.core.async_compat import resolve_maybe_awaitable
from app.core.components import build_runtime_components
from app.core.config import get_settings
from app.workers.processar_jobs import executar_worker_local

settings = get_settings()
components = build_runtime_components(settings)
job_service = components.service
queue_gateway = components.queue
worker_task: asyncio.Task[None] | None = None


def resolver_job_service():
    return job_service


jobs.router.dependency_overrides_provider = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global worker_task
    if settings.enable_async_worker:
        worker_task = asyncio.create_task(executar_worker_local(job_service, queue_gateway))
    yield
    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
    await queue_gateway.fechar()


app = FastAPI(
    title="ReqSys Runtime API",
    version=settings.schema_version,
    description="Runtime executável com workflow assíncrono, fila em memória DEV, worker local e httpx.",
    lifespan=lifespan,
)
app.dependency_overrides[jobs.get_job_service] = resolver_job_service
app.include_router(jobs.router)


@app.get("/health", tags=["runtime"])
async def health() -> dict[str, str]:
    queue_ok = await queue_gateway.ping()
    return {
        "status": "ok" if queue_ok else "degraded",
        "service": settings.service_name,
        "version": settings.schema_version,
    }


@app.get("/api/runtime/health", tags=["runtime"])
async def runtime_health() -> dict[str, object]:
    queue_size = await resolve_maybe_awaitable(queue_gateway.tamanho())
    return {
        "status": "operational" if await queue_gateway.ping() else "degraded",
        "service": settings.service_name,
        "worker_enabled": settings.enable_async_worker,
        "queue_size": queue_size,
    }


@app.get("/api/runtime/analytics", tags=["runtime"])
async def runtime_analytics() -> dict[str, object]:
    return await job_service.metricas()
