from __future__ import annotations

from redis.asyncio import Redis


class RedisQueueGateway:
    """Fila Redis durável com lista de processamento para confirmação explícita."""

    def __init__(
        self,
        redis: Redis,
        queue_name: str,
        processing_queue_name: str,
        block_timeout_seconds: int = 5,
    ) -> None:
        self._redis = redis
        self._queue_name = queue_name
        self._processing_queue_name = processing_queue_name
        self._block_timeout_seconds = block_timeout_seconds
        self._current_job_id: str | None = None

    async def publicar(self, job_id: str) -> None:
        await self._redis.lpush(self._queue_name, job_id)

    async def consumir(self) -> str:
        while True:
            job_id = await self._redis.brpoplpush(
                self._queue_name,
                self._processing_queue_name,
                timeout=self._block_timeout_seconds,
            )
            if job_id is not None:
                self._current_job_id = job_id
                return job_id

    async def confirmar(self) -> None:
        if self._current_job_id is None:
            return
        await self._redis.lrem(self._processing_queue_name, 1, self._current_job_id)
        self._current_job_id = None

    async def tamanho(self) -> int:
        return int(await self._redis.llen(self._queue_name))

    async def ping(self) -> bool:
        return bool(await self._redis.ping())

    async def fechar(self) -> None:
        await self._redis.aclose()
