from __future__ import annotations

from collections import deque

import pytest

from app.infrastructure.queue.redis_queue import RedisQueueGateway


class FakeRedis:
    def __init__(self, processing_jobs: list[str] | None = None) -> None:
        self.lists: dict[str, deque[str]] = {
            "jobs": deque(),
            "processing": deque(processing_jobs or []),
        }

    async def rpoplpush(self, source: str, destination: str) -> str | None:
        source_list = self.lists[source]
        if not source_list:
            return None
        value = source_list.pop()
        self.lists[destination].appendleft(value)
        return value


@pytest.mark.asyncio
async def test_recuperar_jobs_orfaos_retorna_jobs_para_fila_principal() -> None:
    redis = FakeRedis(["JOB-001", "JOB-002"])
    queue = RedisQueueGateway(redis, "jobs", "processing")  # type: ignore[arg-type]

    recuperados = await queue.recuperar_jobs_orfaos()

    assert recuperados == 2
    assert list(redis.lists["processing"]) == []
    assert set(redis.lists["jobs"]) == {"JOB-001", "JOB-002"}


@pytest.mark.asyncio
async def test_recuperar_jobs_orfaos_e_idempotente_com_fila_vazia() -> None:
    redis = FakeRedis()
    queue = RedisQueueGateway(redis, "jobs", "processing")  # type: ignore[arg-type]

    primeira_execucao = await queue.recuperar_jobs_orfaos()
    segunda_execucao = await queue.recuperar_jobs_orfaos()

    assert primeira_execucao == 0
    assert segunda_execucao == 0
    assert list(redis.lists["jobs"]) == []
