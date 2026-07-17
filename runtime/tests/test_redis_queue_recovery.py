from __future__ import annotations

from collections import deque

import pytest

from app.infrastructure.queue.redis_queue import RedisQueueGateway


class FakeRedis:
    def __init__(
        self,
        processing_jobs: list[str] | None = None,
        active_leases: set[str] | None = None,
    ) -> None:
        self.lists: dict[str, deque[str]] = {
            "jobs": deque(),
            "processing": deque(processing_jobs or []),
        }
        self.active_leases = active_leases or set()

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = list(self.lists[key])
        normalized_end = len(values) if end == -1 else end + 1
        return values[start:normalized_end]

    async def exists(self, key: str) -> int:
        return int(key in self.active_leases)

    async def lrem(self, key: str, count: int, value: str) -> int:
        if count != 1:
            raise AssertionError("FakeRedis suporta somente lrem com count=1")

        values = self.lists[key]
        try:
            values.remove(value)
        except ValueError:
            return 0
        return 1

    async def lpush(self, key: str, value: str) -> int:
        self.lists[key].appendleft(value)
        return len(self.lists[key])


@pytest.mark.asyncio
async def test_recuperar_jobs_orfaos_retorna_jobs_para_fila_principal() -> None:
    redis = FakeRedis(["JOB-001", "JOB-002"])
    queue = RedisQueueGateway(redis, "jobs", "processing")  # type: ignore[arg-type]

    recuperados = await queue.recuperar_jobs_orfaos()

    assert recuperados == 2
    assert list(redis.lists["processing"]) == []
    assert set(redis.lists["jobs"]) == {"JOB-001", "JOB-002"}


@pytest.mark.asyncio
async def test_recuperar_jobs_orfaos_preserva_job_com_lease_ativo() -> None:
    redis = FakeRedis(
        ["JOB-ATIVO", "JOB-ORFAO"],
        active_leases={"processing:lease:JOB-ATIVO"},
    )
    queue = RedisQueueGateway(redis, "jobs", "processing")  # type: ignore[arg-type]

    recuperados = await queue.recuperar_jobs_orfaos()

    assert recuperados == 1
    assert list(redis.lists["processing"]) == ["JOB-ATIVO"]
    assert list(redis.lists["jobs"]) == ["JOB-ORFAO"]


@pytest.mark.asyncio
async def test_recuperar_jobs_orfaos_e_idempotente_com_fila_vazia() -> None:
    redis = FakeRedis()
    queue = RedisQueueGateway(redis, "jobs", "processing")  # type: ignore[arg-type]

    primeira_execucao = await queue.recuperar_jobs_orfaos()
    segunda_execucao = await queue.recuperar_jobs_orfaos()

    assert primeira_execucao == 0
    assert segunda_execucao == 0
    assert list(redis.lists["jobs"]) == []
