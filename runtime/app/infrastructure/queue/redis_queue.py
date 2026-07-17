from __future__ import annotations

import uuid

from redis.asyncio import Redis


class RedisQueueGateway:
    """Fila Redis durável com lease distribuído e métricas operacionais."""

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
        lease_renew_interval_seconds: int = 20,
    ) -> None:
        self._redis = redis
        self._queue_name = queue_name
        self._processing_queue_name = processing_queue_name
        self._block_timeout_seconds = block_timeout_seconds
        self._lease_ttl_seconds = lease_ttl_seconds
        self._lease_renew_interval_seconds = lease_renew_interval_seconds
        self._lease_prefix = f"{processing_queue_name}:lease"
        self._metrics_key = f"{processing_queue_name}:lease:metrics"
        self._current_job_id: str | None = None
        self._current_lease_token: str | None = None

    @property
    def lease_renew_interval_seconds(self) -> int:
        return self._lease_renew_interval_seconds

    def _lease_key(self, job_id: str) -> str:
        return f"{self._lease_prefix}:{job_id}"

    async def _incrementar_metrica(self, nome: str, quantidade: int = 1) -> None:
        """Métricas são best-effort e nunca podem interromper o processamento."""
        hincrby = getattr(self._redis, "hincrby", None)
        if hincrby is None:
            return
        try:
            await hincrby(self._metrics_key, nome, quantidade)
        except Exception:  # pragma: no cover - degradação segura de observabilidade
            return

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
                await self._incrementar_metrica("lease_acquired_total")
                return job_id

            await self._incrementar_metrica("lease_contention_total")
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
        metric = "lease_renewed_total" if result else "lease_renew_failed_total"
        await self._incrementar_metrica(metric)
        return bool(result)

    async def confirmar(self) -> None:
        if self._current_job_id is None:
            return
        await self._redis.lrem(self._processing_queue_name, 1, self._current_job_id)
        if self._current_lease_token is not None:
            released = await self._redis.eval(
                self._RELEASE_LEASE_SCRIPT,
                1,
                self._lease_key(self._current_job_id),
                self._current_lease_token,
            )
            await self._incrementar_metrica(
                "lease_released_total" if released else "lease_release_mismatch_total"
            )
        self._current_job_id = None
        self._current_lease_token = None

    async def recuperar_jobs_orfaos(self) -> int:
        recuperados = 0
        job_ids = await self._redis.lrange(self._processing_queue_name, 0, -1)
        for job_id in job_ids:
            if await self._redis.exists(self._lease_key(job_id)):
                continue
            removed = await self._redis.lrem(self._processing_queue_name, 1, job_id)
            if removed:
                await self._redis.lpush(self._queue_name, job_id)
                recuperados += 1
        if recuperados:
            await self._incrementar_metrica("lease_expired_recovered_total", recuperados)
        return recuperados

    async def metricas_operacionais(self) -> dict[str, int]:
        hgetall = getattr(self._redis, "hgetall", None)
        if hgetall is None:
            return {}
        try:
            raw = await hgetall(self._metrics_key)
        except Exception:  # pragma: no cover - degradação segura de observabilidade
            return {}
        return {key: int(value) for key, value in raw.items()}

    async def tamanho(self) -> int:
        return int(await self._redis.llen(self._queue_name))

    async def ping(self) -> bool:
        return bool(await self._redis.ping())

    async def fechar(self) -> None:
        await self._redis.aclose()
