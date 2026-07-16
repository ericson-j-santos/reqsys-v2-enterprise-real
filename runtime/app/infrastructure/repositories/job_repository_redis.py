from __future__ import annotations

from redis.asyncio import Redis

from app.domain.models.job_assincrono import JobAssincrono
from app.infrastructure.repositories.job_repository_memoria import JobNaoEncontradoError


class JobRepositoryRedis:
    def __init__(self, redis: Redis, key_prefix: str, index_key: str, ttl_seconds: int) -> None:
        self._redis = redis
        self._key_prefix = key_prefix
        self._index_key = index_key
        self._ttl_seconds = ttl_seconds

    def _key(self, job_id: str) -> str:
        return f"{self._key_prefix}:{job_id}"

    async def salvar(self, job: JobAssincrono) -> JobAssincrono:
        async with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.set(self._key(job.job_id), job.model_dump_json(), ex=self._ttl_seconds)
            pipeline.sadd(self._index_key, job.job_id)
            await pipeline.execute()
        return job

    async def obter(self, job_id: str) -> JobAssincrono:
        payload = await self._redis.get(self._key(job_id))
        if payload is None:
            raise JobNaoEncontradoError(job_id)
        return JobAssincrono.model_validate_json(payload)

    async def listar(self) -> list[JobAssincrono]:
        job_ids = await self._redis.smembers(self._index_key)
        jobs: list[JobAssincrono] = []
        for job_id in job_ids:
            payload = await self._redis.get(self._key(job_id))
            if payload is not None:
                jobs.append(JobAssincrono.model_validate_json(payload))
        return jobs

    async def metricas_por_status(self) -> dict[str, int]:
        metricas: dict[str, int] = {}
        for job in await self.listar():
            metricas[job.status.value] = metricas.get(job.status.value, 0) + 1
        return metricas

    async def ping(self) -> bool:
        return bool(await self._redis.ping())
