from __future__ import annotations

import pytest

from app.infrastructure.queue.redis_queue import RedisQueueGateway


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.processing = ["job-ativo", "job-orfao"]
        self.queue: list[str] = []

    async def exists(self, key: str) -> int:
        return int(key in self.values)

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        return list(self.processing)

    async def lrem(self, key: str, count: int, value: str) -> int:
        if value not in self.processing:
            return 0
        self.processing.remove(value)
        return 1

    async def lpush(self, key: str, value: str) -> int:
        self.queue.insert(0, value)
        return len(self.queue)


@pytest.mark.asyncio
async def test_recuperacao_preserva_job_com_lease_ativo() -> None:
    redis = FakeRedis()
    queue = RedisQueueGateway(redis, "jobs", "jobs:processing")  # type: ignore[arg-type]
    redis.values[queue._lease_key("job-ativo")] = "worker-a"

    recuperados = await queue.recuperar_jobs_orfaos()

    assert recuperados == 1
    assert redis.processing == ["job-ativo"]
    assert redis.queue == ["job-orfao"]


@pytest.mark.asyncio
async def test_renovar_lease_sem_job_atual_retorna_falso() -> None:
    queue = RedisQueueGateway(FakeRedis(), "jobs", "jobs:processing")  # type: ignore[arg-type]

    assert await queue.renovar_lease() is False
