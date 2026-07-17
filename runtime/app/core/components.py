from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from app.application.services.job_service import JobService
from app.core.config import RuntimeSettings
from app.infrastructure.http.httpx_gateway import HttpxGateway
from app.infrastructure.queue.asyncio_queue import AsyncioQueueGateway
from app.infrastructure.queue.redis_queue import RedisQueueGateway
from app.infrastructure.repositories.job_repository_memoria import JobRepositoryMemoria
from app.infrastructure.repositories.job_repository_redis import JobRepositoryRedis


@dataclass(slots=True)
class RuntimeComponents:
    service: JobService
    queue: Any
    repository: Any



def build_runtime_components(settings: RuntimeSettings) -> RuntimeComponents:
    http_gateway = HttpxGateway()

    if settings.queue_backend == "redis":
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        queue = RedisQueueGateway(
            redis,
            settings.redis_queue_name,
            settings.redis_processing_queue_name,
            settings.redis_block_timeout_seconds,
        )
        repository = JobRepositoryRedis(
            redis,
            settings.redis_job_prefix,
            settings.redis_job_index,
            settings.redis_job_ttl_seconds,
        )
    else:
        queue = AsyncioQueueGateway()
        repository = JobRepositoryMemoria()

    return RuntimeComponents(
        service=JobService(repository, queue, http_gateway, settings),
        queue=queue,
        repository=repository,
    )
