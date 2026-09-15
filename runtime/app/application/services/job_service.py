from __future__ import annotations

import hashlib
import re
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
    TipoOperacao,
)
from app.domain.models.todo_event import TodoEventAcceptedResponse, TodoEventV1, TodoGlobalUpsertResult
from app.infrastructure.http.httpx_gateway import HttpxGateway
from app.infrastructure.queue.errors import QueueCapacityError
from app.observability.lease_slo import avaliar_lease_slo


class TodoEventIdentityConflictError(ValueError):
    """O mesmo event_id foi reutilizado com conteúdo diferente."""


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

        await self._persistir_e_publicar(job)

        return AsyncJobAcceptedResponse(
            job_id=job.job_id,
            correlation_id=job.correlation_id,
            status_url=f"/api/jobs/{job.job_id}",
        )

    async def criar_todo_evento(self, event: TodoEventV1) -> TodoEventAcceptedResponse:
        """Cria atomicamente por event_id e publica de forma idempotente."""
        payload = event.model_dump(mode="json")
        job = JobAssincrono(
            job_id=self._gerar_todo_job_id(event.event_id),
            origem=event.producer or "todo_event",
            tipo_operacao=TipoOperacao.SINCRONIZAR_TODO_GLOBAL,
            destino="todo_global",
            payload=payload,
            correlation_id=event.correlation_id,
            max_tentativas=self._settings.max_tentativas,
            destino_url=self._settings.todo_global_adapter_url,
        )

        criar_se_ausente = getattr(self._repository, "criar_se_ausente", None)
        if criar_se_ausente is None:
            raise RuntimeError("repository_atomic_create_not_supported")
        stored, created = await resolve_maybe_awaitable(criar_se_ausente(job))

        if not created:
            if stored.payload != payload:
                raise TodoEventIdentityConflictError("event_id_reused_with_different_payload")
            # Reassegura entrega se houve queda entre persistência e publicação.
            # Duplicatas de transporte não criam novo efeito lógico: jobs terminais
            # são no-op e o Redis aplica lease por job_id.
            if stored.status == JobStatus.QUEUED:
                try:
                    await self._queue.publicar(stored.job_id)
                except QueueCapacityError:
                    # O evento já está duravelmente persistido como QUEUED. Em replay,
                    # backpressure não invalida o aceite anterior; recovery tentará de novo.
                    pass
            return TodoEventAcceptedResponse(
                event_id=event.event_id,
                job_id=stored.job_id,
                status=stored.status.value,
                correlation_id=stored.correlation_id,
                idempotency_key=str(stored.payload["idempotency_key"]),
                duplicate_event=True,
                status_url=f"/api/jobs/{stored.job_id}",
                message="Evento já persistido; nenhum novo efeito lógico foi criado.",
            )

        try:
            await self._queue.publicar(job.job_id)
        except QueueCapacityError:
            remover = getattr(self._repository, "remover", None)
            if remover is not None:
                await resolve_maybe_awaitable(remover(job.job_id))
            raise

        return TodoEventAcceptedResponse(
            event_id=event.event_id,
            job_id=job.job_id,
            correlation_id=event.correlation_id,
            idempotency_key=event.idempotency_key,
            status_url=f"/api/jobs/{job.job_id}",
        )

    async def consultar_job(self, job_id: str):
        job = await self._repository.obter(job_id)
        return job.to_status_response()

    async def consultar_todo_evento(self, event_id: str):
        return await self.consultar_job(self._gerar_todo_job_id(event_id))

    async def processar_job(self, job_id: str) -> None:
        job = await self._repository.obter(job_id)
        if job.status in {JobStatus.COMPLETED, JobStatus.DEAD_LETTER}:
            return

        job.registrar_tentativa()
        job.atualizar_status(JobStatus.PROCESSING)
        await self._repository.salvar(job)

        try:
            resultado = await self._executar_operacao(job)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            await self._registrar_falha(job, self._sanitizar_erro(str(exc)))
            return

        job.atualizar_status(JobStatus.COMPLETED, resultado=resultado)
        await self._repository.salvar(job)

    async def recuperar_jobs_pendentes(self) -> int:
        """Rede de segurança para o gap persistência -> publicação após reinício."""
        recuperados = 0
        for job in await self._repository.listar():
            if job.status != JobStatus.QUEUED:
                continue
            try:
                await self._queue.publicar(job.job_id)
            except QueueCapacityError:
                break
            recuperados += 1
        return recuperados

    async def metricas(self) -> dict[str, Any]:
        por_status = await self._repository.metricas_por_status()
        queue_size = await resolve_maybe_awaitable(self._queue.tamanho())
        dlq_size = 0
        tamanho_dlq = getattr(self._queue, "tamanho_dlq", None)
        if tamanho_dlq is not None:
            dlq_size = int(await resolve_maybe_awaitable(tamanho_dlq()))
        metricas_lease: dict[str, int] = {}
        coletar_metricas = getattr(self._queue, "metricas_operacionais", None)
        if coletar_metricas is not None:
            metricas_lease = await resolve_maybe_awaitable(coletar_metricas())
        return {
            "schema_version": self._settings.schema_version,
            "queue_backend": self._settings.queue_backend,
            "storage_backend": self._settings.storage_backend,
            "queue_size": queue_size,
            "dlq_size": dlq_size,
            "max_queue_size": self._settings.max_queue_size,
            "jobs_por_status": por_status,
            "lease": {
                "ttl_seconds": self._settings.redis_lease_ttl_seconds,
                "renew_interval_seconds": self._settings.redis_lease_renew_interval_seconds,
                "metrics": metricas_lease,
                "slo": avaliar_lease_slo(metricas_lease),
            },
        }

    async def _persistir_e_publicar(self, job: JobAssincrono) -> None:
        await self._repository.salvar(job)
        try:
            await self._queue.publicar(job.job_id)
        except QueueCapacityError:
            remover = getattr(self._repository, "remover", None)
            if remover is not None:
                await resolve_maybe_awaitable(remover(job.job_id))
            raise

    async def _executar_operacao(self, job: JobAssincrono) -> dict[str, Any]:
        if job.tipo_operacao == TipoOperacao.SINCRONIZAR_TODO_GLOBAL:
            if not job.destino_url:
                raise RuntimeError("todo_global_adapter_not_configured")
            raw = await self._http_gateway.post_json(job.destino_url, job.payload, job.correlation_id)
            result = TodoGlobalUpsertResult.model_validate(raw)
            expected_key = str(job.payload["idempotency_key"])
            expected_status = str(job.payload["todo"]["status"])
            if result.idempotency_key != expected_key:
                raise RuntimeError("todo_global_adapter_identity_mismatch")
            if result.canonical_status.value != expected_status:
                raise RuntimeError("todo_global_adapter_status_mismatch")
            if not result.readback_verified:
                raise RuntimeError("todo_global_adapter_readback_not_verified")
            return result.model_dump(mode="json")

        if job.destino_url:
            return await self._http_gateway.post_json(job.destino_url, job.payload, job.correlation_id)

        return {
            "modo": "simulado_dev",
            "destino": job.destino,
            "tipo_operacao": job.tipo_operacao.value,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _registrar_falha(self, job: JobAssincrono, erro: str) -> None:
        if job.tentativas >= job.max_tentativas:
            await self._mover_para_dlq(job, erro)
            return

        job.atualizar_status(JobStatus.RETRYING, erro=erro)
        await self._repository.salvar(job)
        delay = min(
            self._settings.retry_backoff_base_seconds * (2 ** max(job.tentativas - 1, 0)),
            self._settings.retry_backoff_max_seconds,
        )
        try:
            await self._queue.publicar(job.job_id, delay_seconds=delay)
        except QueueCapacityError:
            await self._mover_para_dlq(job, "retry_queue_capacity_exceeded")

    async def _mover_para_dlq(self, job: JobAssincrono, erro: str) -> None:
        job.atualizar_status(JobStatus.DEAD_LETTER, erro=self._sanitizar_erro(erro))
        await self._repository.salvar(job)
        quarentenar = getattr(self._queue, "quarentenar", None)
        if quarentenar is not None:
            await resolve_maybe_awaitable(quarentenar(job.job_id))

    @staticmethod
    def _sanitizar_erro(erro: str) -> str:
        sanitized = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", erro)
        sanitized = re.sub(r"(?i)(token|secret|password|api[_-]?key)=([^&\s]+)", r"\1=[REDACTED]", sanitized)
        return sanitized[:500]

    @staticmethod
    def _gerar_job_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        sufixo = uuid.uuid4().hex[:8].upper()
        return f"JOB-{timestamp}-{sufixo}"

    @staticmethod
    def _gerar_todo_job_id(event_id: str) -> str:
        digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest().upper()
        return f"TODOEVENT-{digest}"
