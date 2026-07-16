from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, model_validator


class RuntimeSettings(BaseModel):
    service_name: str = "reqsys-runtime"
    schema_version: str = "0.7.0"
    enable_async_worker: bool = False
    queue_backend: str = "memory"
    storage_backend: str = "memory"
    redis_url: str = "redis://localhost:6379/0"
    redis_queue_name: str = "reqsys:runtime:jobs"
    redis_processing_queue_name: str = "reqsys:runtime:jobs:processing"
    redis_job_prefix: str = "reqsys:runtime:job"
    redis_job_index: str = "reqsys:runtime:jobs:index"
    redis_block_timeout_seconds: int = 5
    redis_job_ttl_seconds: int = 604800
    max_tentativas: int = 3

    @model_validator(mode="after")
    def validar_backends(self) -> "RuntimeSettings":
        queue_backend = self.queue_backend.lower()
        storage_backend = self.storage_backend.lower()
        if queue_backend not in {"memory", "redis"}:
            raise ValueError("QUEUE_BACKEND deve ser 'memory' ou 'redis'")
        if storage_backend not in {"memory", "redis"}:
            raise ValueError("STORAGE_BACKEND deve ser 'memory' ou 'redis'")
        if queue_backend == "redis" and storage_backend != "redis":
            raise ValueError("QUEUE_BACKEND=redis exige STORAGE_BACKEND=redis para worker desacoplado")
        self.queue_backend = queue_backend
        self.storage_backend = storage_backend
        return self


@lru_cache
def get_settings() -> RuntimeSettings:
    return RuntimeSettings(
        enable_async_worker=os.getenv("ENABLE_ASYNC_WORKER", "false").lower() == "true",
        queue_backend=os.getenv("QUEUE_BACKEND", "memory"),
        storage_backend=os.getenv("STORAGE_BACKEND", "memory"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        redis_queue_name=os.getenv("REDIS_QUEUE_NAME", "reqsys:runtime:jobs"),
        redis_processing_queue_name=os.getenv("REDIS_PROCESSING_QUEUE_NAME", "reqsys:runtime:jobs:processing"),
        redis_job_prefix=os.getenv("REDIS_JOB_PREFIX", "reqsys:runtime:job"),
        redis_job_index=os.getenv("REDIS_JOB_INDEX", "reqsys:runtime:jobs:index"),
        redis_block_timeout_seconds=int(os.getenv("REDIS_BLOCK_TIMEOUT_SECONDS", "5")),
        redis_job_ttl_seconds=int(os.getenv("REDIS_JOB_TTL_SECONDS", "604800")),
        max_tentativas=int(os.getenv("ASYNC_JOB_MAX_TENTATIVAS", "3")),
    )
