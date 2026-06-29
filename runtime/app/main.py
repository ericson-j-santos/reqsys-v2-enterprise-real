from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api import jobs
from app.application.services.job_service import JobService
from app.core.config import get_settings
from app.infrastructure.http.httpx_gateway import HttpxGateway
from app.infrastructure.queue.asyncio_queue import AsyncioQueueGateway
from app.infrastructure.repositories.job_repository_memoria import JobRepositoryMemoria
from app.workers.processar_jobs import executar_worker_local

settings = get_settings()
repository = JobRepositoryMemoria()
queue_gateway = AsyncioQueueGateway()
http_gateway = HttpxGateway()
job_service = JobService(repository, queue_gateway, http_gateway, settings)
worker_task: asyncio.Task[None] | None = None


def resolver_job_service() -> JobService:
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
    return {"status": "ok", "service": settings.service_name, "version": settings.schema_version}


@app.get("/api/runtime/health", tags=["runtime"])
async def runtime_health() -> dict[str, object]:
    return {
        "status": "operational",
        "service": settings.service_name,
        "worker_enabled": settings.enable_async_worker,
        "queue_size": queue_gateway.tamanho(),
    }


@app.get("/api/runtime/analytics", tags=["runtime"])
async def runtime_analytics() -> dict[str, object]:
    return await job_service.metricas()
