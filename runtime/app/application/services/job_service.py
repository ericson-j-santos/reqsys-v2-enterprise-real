from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.async_compat import resolve_maybe_awaitable
from app.core.config import RuntimeSettings
from app.domain.models.job_assincrono import (
    AsyncJobAcceptedResponse,
    AsyncJobCreateRequest,
    JobAssincrono,
    JobStatus,
)
from app.infrastructure.http.httpx_gateway import HttpxGateway


class JobService:
    def __init__(
        self,
        repository: Any,
        queue: Any,
        http_gateway: HttpxGateway,
        settings: RuntimeSettings,
    ) -> None:
        self._repository = repository
        self._queue = queue
        self._http_gateway = http_gateway
        self._settings = settings

    async def criar_job(self, request: AsyncJobCreateRequest) -> AsyncJobAcceptedResponse:
        correlation_id = request.metadata.correlation_id or f"reqsys-{uuid.uuid4()}"
        job_id = self._gerar_job_id()

        job = JobAssincrono(
            job_id=job_id,
            origem=request.origem,
            tipo_operacao=request.tipo_operacao,
            destino=request.destino,
            payload=request.payload,
            correlation_id=correlation_id,
            max_tentativas=self._settings.max_tentativas,
            destino_url=str(request.destino_url) if request.destino_url else None,
        )

        await self._repository.salvar(job)
        await self._queue.publicar(job.job_id)

        return AsyncJobAcceptedResponse(
            job_id=job.job_id,
            correlation_id=job.correlation_id,
            status_url=f"/api/jobs/{job.job_id}",
        )

    async def consultar_job(self, job_id: str):
        job = await self._repository.obter(job_id)
        return job.to_status_response()

    async def processar_job(self, job_id: str) -> None:
        job = await self._repository.obter(job_id)
        job.registrar_tentativa()
        job.atualizar_status(JobStatus.PROCESSING)
        await self._repository.salvar(job)

        try:
            resultado = await self._executar_operacao(job)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            await self._registrar_falha(job, str(exc))
            return

        job.atualizar_status(JobStatus.COMPLETED, resultado=resultado)
        await self._repository.salvar(job)

    async def metricas(self) -> dict[str, Any]:
        por_status = await self._repository.metricas_por_status()
        queue_size = await resolve_maybe_awaitable(self._queue.tamanho())
        metricas_lease: dict[str, int] = {}
        coletar_metricas = getattr(self._queue, "metricas_operacionais", None)
        if coletar_metricas is not None:
            metricas_lease = await resolve_maybe_awaitable(coletar_metricas())
        return {
            "schema_version": self._settings.schema_version,
            "queue_backend": self._settings.queue_backend,
            "storage_backend": self._settings.storage_backend,
            "queue_size": queue_size,
            "jobs_por_status": por_status,
            "lease": {
                "ttl_seconds": self._settings.redis_lease_ttl_seconds,
                "renew_interval_seconds": self._settings.redis_lease_renew_interval_seconds,
                "metrics": metricas_lease,
            },
        }

    async def _executar_operacao(self, job: JobAssincrono) -> dict[str, Any]:
        if job.destino_url:
            return await self._http_gateway.post_json(job.destino_url, job.payload, job.correlation_id)

        return {
            "modo": "simulado_dev",
            "destino": job.destino,
            "tipo_operacao": job.tipo_operacao.value,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _registrar_falha(self, job: JobAssincrono, erro: str) -> None:
        proximo_status = JobStatus.RETRYING if job.tentativas < job.max_tentativas else JobStatus.DEAD_LETTER
        job.atualizar_status(proximo_status, erro=erro)
        await self._repository.salvar(job)

        if proximo_status == JobStatus.RETRYING:
            await self._queue.publicar(job.job_id)

    @staticmethod
    def _gerar_job_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        sufixo = uuid.uuid4().hex[:8].upper()
        return f"JOB-{timestamp}-{sufixo}"
