from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api import central, jobs, parallelism_control, parallelism_reconciliation, todo_events
from app.application.services.central_service import CentralService
from app.application.services.central_worker import CentralWorker
from app.domain.central.wip_policy import WipPolicy
from app.infrastructure.executors.registry import registry_de_configuracao
from app.infrastructure.repositories.central_store import (
    CentralStore,
    InMemoryCentralStore,
    RedisCentralStore,
)
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
reconciliation_task: asyncio.Task[None] | None = None
runtime_redis: Redis | None = None

if settings.storage_backend == "redis":
    # Um único cliente serve o controle de paralelismo e a Central.
    runtime_redis = Redis.from_url(settings.redis_url, decode_responses=True)
    parallelism_store: parallelism_control.ParallelismStore = parallelism_control.RedisParallelismStore(
        runtime_redis, settings.parallelism_control_redis_prefix
    )
    central_store: CentralStore = RedisCentralStore(runtime_redis, settings.central_redis_prefix)
else:
    parallelism_store = parallelism_control.InMemoryParallelismStore()
    central_store = InMemoryCentralStore()

central_service = CentralService(
    wip_policy=WipPolicy(settings.central_max_active_root_causes),
    store=central_store,
)
executor_registry = registry_de_configuracao(
    settings.central_executor_endpoints,
    service_token=settings.central_executor_service_token,
    github_token=settings.central_github_token,
)
central_worker = CentralWorker(
    central_service,
    executor_registry,
    intervalo_ocioso_segundos=settings.central_worker_idle_seconds,
)
central_worker_task: asyncio.Task[None] | None = None


async def resolver_smoke_check(target: parallelism_control.Target) -> dict[str, object]:
    if target == "api":
        return {"healthy": True, "service": settings.service_name}
    if target == "queue":
        queue_size = await resolve_maybe_awaitable(queue_gateway.tamanho())
        return {"healthy": queue_size >= 0, "queue_size": queue_size}
    running = bool(worker_task and not worker_task.done())
    return {"healthy": settings.enable_async_worker and running, "worker_enabled": settings.enable_async_worker}


validation_slo_seconds = int(os.getenv("PARALLELISM_VALIDATION_SLO_SECONDS", "300"))
reconciliation_interval_seconds = int(os.getenv("PARALLELISM_RECONCILIATION_INTERVAL_SECONDS", "30"))
parallelism_reconciler = parallelism_reconciliation.ParallelismReconciler(
    parallelism_store,
    resolver_smoke_check,
    validation_slo_seconds=validation_slo_seconds,
)


def resolver_job_service() -> JobService:
    return job_service


def resolver_central_service() -> CentralService:
    return central_service


def resolver_central_worker() -> CentralWorker:
    return central_worker


def resolver_worker_cycle_enabled() -> bool:
    # Em produção o ciclo é do worker contínuo, não de um POST manual.
    return settings.runtime_environment != "prod"


def resolver_parallelism_store() -> parallelism_control.ParallelismStore:
    return parallelism_store


def resolver_control_token() -> str:
    if settings.runtime_environment == "prod":
        return ""
    return settings.parallelism_control_token


def resolver_reconciler() -> parallelism_reconciliation.ParallelismReconciler:
    return parallelism_reconciler


async def run_reconciliation_loop() -> None:
    while True:
        await asyncio.sleep(reconciliation_interval_seconds)
        await parallelism_reconciler.reconcile_all()


jobs.router.dependency_overrides_provider = None
todo_events.router.dependency_overrides_provider = None
parallelism_control.router.dependency_overrides_provider = None
parallelism_reconciliation.router.dependency_overrides_provider = None
central.router.dependency_overrides_provider = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global worker_task, reconciliation_task, central_worker_task
    if settings.central_worker_enabled:
        central_worker_task = asyncio.create_task(central_worker.executar_continuamente())
    if settings.enable_async_worker:
        worker_task = asyncio.create_task(executar_worker_local(job_service, queue_gateway))
    if settings.runtime_environment != "prod":
        reconciliation_task = asyncio.create_task(run_reconciliation_loop())
    yield
    for task in (central_worker_task, reconciliation_task, worker_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    await queue_gateway.fechar()
    if runtime_redis is not None:
        await runtime_redis.aclose()


app = FastAPI(
    title="ReqSys Runtime API",
    version=settings.schema_version,
    description="Runtime executável com workflow assíncrono, fila governada e controle de paralelismo.",
    lifespan=lifespan,
)
app.dependency_overrides[jobs.get_job_service] = resolver_job_service
app.dependency_overrides[todo_events.get_job_service] = resolver_job_service
app.dependency_overrides[parallelism_control.get_parallelism_store] = resolver_parallelism_store
app.dependency_overrides[parallelism_control.get_control_token] = resolver_control_token
app.dependency_overrides[parallelism_control.get_smoke_check] = lambda: resolver_smoke_check
app.dependency_overrides[parallelism_reconciliation.get_reconciler] = resolver_reconciler
app.dependency_overrides[central.get_central_service] = resolver_central_service
app.dependency_overrides[central.get_central_worker] = resolver_central_worker
app.dependency_overrides[central.get_worker_cycle_enabled] = resolver_worker_cycle_enabled
app.include_router(jobs.router)
app.include_router(todo_events.router)
app.include_router(parallelism_control.router)
app.include_router(parallelism_reconciliation.router)
app.include_router(central.router)


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
        "parallelism_reconciliation_enabled": settings.runtime_environment != "prod",
        "parallelism_validation_slo_seconds": validation_slo_seconds,
        "central_worker_enabled": settings.central_worker_enabled,
        "central_executors": [item.value for item in executor_registry.configurados()],
    }


@app.get("/api/runtime/build-info", tags=["runtime"])
async def runtime_build_info() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.runtime_environment,
        "build_sha": (os.getenv("GITHUB_SHA") or "unknown").strip() or "unknown",
        "schema_version": settings.schema_version,
    }


@app.get("/api/runtime/analytics", tags=["runtime"])
async def runtime_analytics() -> dict[str, object]:
    metrics = await job_service.metricas()
    metrics["parallelism_reconciliation"] = parallelism_reconciler.metrics.snapshot()
    metrics["central"] = (await central_service.metricas()).to_dict()
    return metrics
