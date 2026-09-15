from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, model_validator


class RuntimeSettings(BaseModel):
    service_name: str = "reqsys-runtime"
    schema_version: str = "0.7.0"
    runtime_environment: str = "dev"
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
    redis_lease_ttl_seconds: int = 60
    redis_lease_renew_interval_seconds: int = 20
    max_queue_size: int = 1000
    retry_backoff_base_seconds: float = 1.0
    retry_backoff_max_seconds: float = 60.0
    todo_global_adapter_url: str | None = None
    todo_global_service_token: str = ""
    parallelism_control_token: str = ""
    parallelism_control_redis_prefix: str = "reqsys:runtime:parallelism"
    max_tentativas: int = 3

    @model_validator(mode="after")
    def validar_backends(self) -> "RuntimeSettings":
        queue_backend = self.queue_backend.lower()
        storage_backend = self.storage_backend.lower()
        environment = self.runtime_environment.lower()
        if queue_backend not in {"memory", "redis"}:
            raise ValueError("QUEUE_BACKEND deve ser 'memory' ou 'redis'")
        if storage_backend not in {"memory", "redis"}:
            raise ValueError("STORAGE_BACKEND deve ser 'memory' ou 'redis'")
        if queue_backend == "redis" and storage_backend != "redis":
            raise ValueError("QUEUE_BACKEND=redis exige STORAGE_BACKEND=redis para worker desacoplado")
        if environment not in {"dev", "stg", "prod", "test"}:
            raise ValueError("RUNTIME_ENVIRONMENT deve ser dev, stg, prod ou test")
        if self.redis_lease_ttl_seconds < 5:
            raise ValueError("REDIS_LEASE_TTL_SECONDS deve ser >= 5")
        if self.redis_lease_renew_interval_seconds < 1:
            raise ValueError("REDIS_LEASE_RENEW_INTERVAL_SECONDS deve ser >= 1")
        if self.redis_lease_renew_interval_seconds >= self.redis_lease_ttl_seconds:
            raise ValueError("REDIS_LEASE_RENEW_INTERVAL_SECONDS deve ser menor que REDIS_LEASE_TTL_SECONDS")
        if self.max_queue_size < 1:
            raise ValueError("MAX_QUEUE_SIZE deve ser >= 1")
        if self.retry_backoff_base_seconds < 0:
            raise ValueError("RETRY_BACKOFF_BASE_SECONDS deve ser >= 0")
        if self.retry_backoff_max_seconds < self.retry_backoff_base_seconds:
            raise ValueError("RETRY_BACKOFF_MAX_SECONDS deve ser >= RETRY_BACKOFF_BASE_SECONDS")
        self.queue_backend = queue_backend
        self.storage_backend = storage_backend
        self.runtime_environment = environment
        return self


@lru_cache
def get_settings() -> RuntimeSettings:
    return RuntimeSettings(
        runtime_environment=os.getenv("RUNTIME_ENVIRONMENT", "dev"),
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
        redis_lease_ttl_seconds=int(os.getenv("REDIS_LEASE_TTL_SECONDS", "60")),
        redis_lease_renew_interval_seconds=int(os.getenv("REDIS_LEASE_RENEW_INTERVAL_SECONDS", "20")),
        max_queue_size=int(os.getenv("MAX_QUEUE_SIZE", "1000")),
        retry_backoff_base_seconds=float(os.getenv("RETRY_BACKOFF_BASE_SECONDS", "1")),
        retry_backoff_max_seconds=float(os.getenv("RETRY_BACKOFF_MAX_SECONDS", "60")),
        todo_global_adapter_url=os.getenv("TODO_GLOBAL_ADAPTER_URL") or None,
        todo_global_service_token=os.getenv("TODO_GLOBAL_ADAPTER_SERVICE_TOKEN", ""),
        parallelism_control_token=os.getenv("REQSYS_PARALLELISM_CONTROL_TOKEN", ""),
        parallelism_control_redis_prefix=os.getenv(
            "PARALLELISM_CONTROL_REDIS_PREFIX", "reqsys:runtime:parallelism"
        ),
        max_tentativas=int(os.getenv("ASYNC_JOB_MAX_TENTATIVAS", "3")),
    )
