from __future__ import annotations

import uuid

from redis.asyncio import Redis


class RedisQueueGateway:
    """Fila Redis durável com confirmação explícita, recuperação e lease por job."""

    _RELEASE_LEASE_SCRIPT = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
      return redis.call('del', KEYS[1])
    end
    return 0
    """

    _RENEW_LEASE_SCRIPT = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
      return redis.call('expire', KEYS[1], ARGV[2])
    end
    return 0
    """

    def __init__(
        self,
        redis: Redis,
        queue_name: str,
        processing_queue_name: str,
        block_timeout_seconds: int = 5,
        lease_ttl_seconds: int = 60,
    ) -> None:
        self._redis = redis
        self._queue_name = queue_name
        self._processing_queue_name = processing_queue_name
        self._block_timeout_seconds = block_timeout_seconds
        self._lease_ttl_seconds = lease_ttl_seconds
        self._lease_prefix = f"{processing_queue_name}:lease"
        self._current_job_id: str | None = None
        self._current_lease_token: str | None = None

    def _lease_key(self, job_id: str) -> str:
        return f"{self._lease_prefix}:{job_id}"

    async def publicar(self, job_id: str) -> None:
        await self._redis.lpush(self._queue_name, job_id)

    async def consumir(self) -> str:
        while True:
            job_id = await self._redis.brpoplpush(
                self._queue_name,
                self._processing_queue_name,
                timeout=self._block_timeout_seconds,
            )
            if job_id is None:
                continue

            token = uuid.uuid4().hex
            acquired = await self._redis.set(
                self._lease_key(job_id), token, ex=self._lease_ttl_seconds, nx=True
            )
            if acquired:
                self._current_job_id = job_id
                self._current_lease_token = token
                return job_id

            await self._redis.lrem(self._processing_queue_name, 1, job_id)
            await self._redis.lpush(self._queue_name, job_id)

    async def renovar_lease(self) -> bool:
        if self._current_job_id is None or self._current_lease_token is None:
            return False
        result = await self._redis.eval(
            self._RENEW_LEASE_SCRIPT,
            1,
            self._lease_key(self._current_job_id),
            self._current_lease_token,
            self._lease_ttl_seconds,
        )
        return bool(result)

    async def confirmar(self) -> None:
        if self._current_job_id is None:
            return
        await self._redis.lrem(self._processing_queue_name, 1, self._current_job_id)
        if self._current_lease_token is not None:
            await self._redis.eval(
                self._RELEASE_LEASE_SCRIPT,
                1,
                self._lease_key(self._current_job_id),
                self._current_lease_token,
            )
        self._current_job_id = None
        self._current_lease_token = None

    async def recuperar_jobs_orfaos(self) -> int:
        """Recupera apenas jobs sem lease ativo, preservando processamento válido."""
        recuperados = 0
        job_ids = await self._redis.lrange(self._processing_queue_name, 0, -1)
        for job_id in job_ids:
            if await self._redis.exists(self._lease_key(job_id)):
                continue
            removed = await self._redis.lrem(self._processing_queue_name, 1, job_id)
            if removed:
                await self._redis.lpush(self._queue_name, job_id)
                recuperados += 1
        return recuperados

    async def tamanho(self) -> int:
        return int(await self._redis.llen(self._queue_name))

    async def ping(self) -> bool:
        return bool(await self._redis.ping())

    async def fechar(self) -> None:
        await self._redis.aclose()
