from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api import jobs
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
    description="Runtime assíncrono com fila durável Redis, worker desacoplado e fallback local.",
    lifespan=lifespan,
)
app.dependency_overrides[jobs.get_job_service] = resolver_job_service
app.include_router(jobs.router)


@app.get("/health", tags=["runtime"])
async def health() -> dict[str, object]:
    queue_ok = await queue_gateway.ping()
    return {
        "status": "ok" if queue_ok else "degraded",
        "service": settings.service_name,
        "version": settings.schema_version,
        "queue_backend": settings.queue_backend,
        "storage_backend": settings.storage_backend,
    }


@app.get("/api/runtime/health", tags=["runtime"])
async def runtime_health() -> dict[str, object]:
    return {
        "status": "operational" if await queue_gateway.ping() else "degraded",
        "service": settings.service_name,
        "worker_enabled_in_api": settings.enable_async_worker,
        "queue_backend": settings.queue_backend,
        "storage_backend": settings.storage_backend,
        "queue_size": await queue_gateway.tamanho(),
    }


@app.get("/api/runtime/analytics", tags=["runtime"])
async def runtime_analytics() -> dict[str, object]:
    return await job_service.metricas()
