from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api import jobs, parallelism_control
from app.application.services.job_service import JobService
from app.core.async_compat import resolve_maybe_awaitable
from app.core.components import build_runtime_components
from app.core.config import get_settings
from app.workers.processar_jobs import executar_worker_local

settings = get_settings()
components = build_runtime_components(settings)
job_service = components.service
queue_gateway = components.queue
worker_task: asyncio.Task[None] | None = None
parallelism_redis: Redis | None = None

if settings.storage_backend == "redis":
    parallelism_redis = Redis.from_url(settings.redis_url, decode_responses=True)
    parallelism_store: parallelism_control.ParallelismStore = parallelism_control.RedisParallelismStore(
        parallelism_redis, settings.parallelism_control_redis_prefix
    )
else:
    parallelism_store = parallelism_control.InMemoryParallelismStore()


def resolver_job_service() -> JobService:
    return job_service


def resolver_parallelism_store() -> parallelism_control.ParallelismStore:
    return parallelism_store


def resolver_control_token() -> str:
    if settings.runtime_environment == "prod":
        return ""
    return settings.parallelism_control_token


async def resolver_smoke_check(target: parallelism_control.Target) -> dict[str, object]:
    if target == "api":
        return {"healthy": True, "service": settings.service_name}
    if target == "queue":
        queue_size = await resolve_maybe_awaitable(queue_gateway.tamanho())
        return {"healthy": queue_size >= 0, "queue_size": queue_size}
    running = bool(worker_task and not worker_task.done())
    return {"healthy": settings.enable_async_worker and running, "worker_enabled": settings.enable_async_worker}


jobs.router.dependency_overrides_provider = None
parallelism_control.router.dependency_overrides_provider = None


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
    if parallelism_redis is not None:
        await parallelism_redis.aclose()


app = FastAPI(
    title="ReqSys Runtime API",
    version=settings.schema_version,
    description="Runtime executável com workflow assíncrono, fila governada e controle de paralelismo.",
    lifespan=lifespan,
)
app.dependency_overrides[jobs.get_job_service] = resolver_job_service
app.dependency_overrides[parallelism_control.get_parallelism_store] = resolver_parallelism_store
app.dependency_overrides[parallelism_control.get_control_token] = resolver_control_token
app.dependency_overrides[parallelism_control.get_smoke_check] = lambda: resolver_smoke_check
app.include_router(jobs.router)
app.include_router(parallelism_control.router)


@app.get("/health", tags=["runtime"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name, "version": settings.schema_version}


@app.get("/api/runtime/health", tags=["runtime"])
async def runtime_health() -> dict[str, object]:
    queue_size = await resolve_maybe_awaitable(queue_gateway.tamanho())
    return {
        "status": "operational",
        "service": settings.service_name,
        "worker_enabled": settings.enable_async_worker,
        "queue_size": queue_size,
        "environment": settings.runtime_environment,
    }


@app.get("/api/runtime/analytics", tags=["runtime"])
async def runtime_analytics() -> dict[str, object]:
    return await job_service.metricas()
