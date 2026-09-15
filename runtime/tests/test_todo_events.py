from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.application.services.job_service import JobService, TodoEventIdentityConflictError
from app.core.config import RuntimeSettings
from app.domain.models.job_assincrono import JobStatus
from app.domain.models.todo_event import TodoEventV1
from app.infrastructure.http.httpx_gateway import HttpxGateway
from app.infrastructure.queue.asyncio_queue import AsyncioQueueGateway
from app.infrastructure.queue.errors import QueueCapacityError
from app.infrastructure.repositories.job_repository_memoria import JobRepositoryMemoria
from app.main import app


class TodoUpsertGateway(HttpxGateway):
    def __init__(self, fail: bool = False, readback_verified: bool = True) -> None:
        self.fail = fail
        self.readback_verified = readback_verified
        self.todos: dict[str, dict] = {}
        self.calls: list[dict] = []

    async def post_json(self, url: str, payload: dict, correlation_id: str) -> dict:
        if self.fail:
            raise RuntimeError("adapter_temporarily_unavailable")
        self.calls.append(payload)
        key = payload["idempotency_key"]
        effect = "updated" if key in self.todos else "created"
        self.todos[key] = payload["todo"]
        return {
            "todo_id": f"todo-{key[:12]}",
            "idempotency_key": key,
            "effect": effect,
            "canonical_status": payload["todo"]["status"],
            "readback_verified": self.readback_verified,
            "correlation_id": correlation_id,
        }


def _key(project: str, tipo: str, external_id: str) -> str:
    return hashlib.sha256(f"{project.lower()}|{tipo.lower()}|{external_id.lower()}".encode()).hexdigest()


def _event(
    *,
    event_id: str,
    status: str = "PENDENTE",
    idempotency_key: str | None = None,
    evidence: str | None = None,
    completion_criteria: str | None = None,
    blocker: str | None = None,
    next_action: str | None = None,
) -> TodoEventV1:
    return TodoEventV1.model_validate(
        {
            "schema_version": "1.0",
            "event_id": event_id,
            "event_type": "todo.updated",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "correlation_id": f"corr-{event_id}",
            "idempotency_key": idempotency_key or _key("ReqSys", "Implementação", "reqsys#1693"),
            "project": "ReqSys",
            "producer": "pytest",
            "todo": {
                "title": "Integrar TODO Global com ReqSys",
                "type": "Implementação",
                "external_id": "reqsys#1693",
                "status": status,
                "priority": "P1",
                "blocker": blocker,
                "next_action": next_action,
                "completion_criteria": completion_criteria,
                "evidence": evidence,
                "e2e_status": "PENDENTE",
                "source": "ReqSys",
            },
        }
    )


def _service(
    *,
    gateway: HttpxGateway | None = None,
    max_queue_size: int = 1000,
    max_attempts: int = 3,
    adapter_url: str | None = "https://todo-global.example/upsert",
):
    repository = JobRepositoryMemoria()
    queue = AsyncioQueueGateway(max_queue_size=max_queue_size)
    settings = RuntimeSettings(
        max_tentativas=max_attempts,
        max_queue_size=max_queue_size,
        retry_backoff_base_seconds=0,
        retry_backoff_max_seconds=0,
        todo_global_adapter_url=adapter_url,
    )
    service = JobService(repository, queue, gateway or TodoUpsertGateway(), settings)
    return service, repository, queue


async def _drain(service: JobService, queue: AsyncioQueueGateway) -> None:
    quantidade = queue.tamanho()
    for _ in range(quantidade):
        job_id = await queue.consumir()
        await service.processar_job(job_id)
        queue.confirmar()


@pytest.mark.asyncio
async def test_replay_do_mesmo_event_id_nao_cria_novo_efeito_logico() -> None:
    gateway = TodoUpsertGateway()
    service, repository, queue = _service(gateway=gateway)
    event = _event(event_id="evt-todo-0001")

    first = await service.criar_todo_evento(event)
    second = await service.criar_todo_evento(event)
    await _drain(service, queue)

    assert first.job_id == second.job_id
    assert first.duplicate_event is False
    assert second.duplicate_event is True
    assert len(await repository.listar()) == 1
    assert len(gateway.calls) == 1
    assert (await service.consultar_job(first.job_id)).tentativas == 1


@pytest.mark.asyncio
async def test_replay_concorrente_do_mesmo_event_id_e_atomicamente_deduplicado() -> None:
    gateway = TodoUpsertGateway()
    service, repository, queue = _service(gateway=gateway)
    event = _event(event_id="evt-todo-concurrent-0001")

    accepted = await asyncio.gather(*(service.criar_todo_evento(event) for _ in range(10)))
    await _drain(service, queue)

    assert len({item.job_id for item in accepted}) == 1
    assert sum(item.duplicate_event for item in accepted) == 9
    assert len(await repository.listar()) == 1
    assert len(gateway.calls) == 1


@pytest.mark.asyncio
async def test_reuso_do_event_id_com_payload_diferente_e_conflito() -> None:
    service, _, _ = _service()
    await service.criar_todo_evento(_event(event_id="evt-todo-conflict-0001"))

    with pytest.raises(TodoEventIdentityConflictError, match="event_id_reused"):
        await service.criar_todo_evento(
            _event(event_id="evt-todo-conflict-0001", status="EM ANDAMENTO")
        )


@pytest.mark.asyncio
async def test_novo_event_id_mesma_idempotency_key_atualiza_um_todo_logico() -> None:
    gateway = TodoUpsertGateway()
    service, _, queue = _service(gateway=gateway)
    key = _key("ReqSys", "Implementação", "reqsys#1693")
    first = await service.criar_todo_evento(_event(event_id="evt-todo-0002", idempotency_key=key))
    second = await service.criar_todo_evento(
        _event(event_id="evt-todo-0003", status="EM ANDAMENTO", idempotency_key=key)
    )

    for accepted in (first, second):
        queued_job = await queue.consumir()
        assert queued_job == accepted.job_id
        await service.processar_job(queued_job)
        queue.confirmar()

    assert len(gateway.todos) == 1
    assert gateway.todos[key]["status"] == "EM ANDAMENTO"
    assert len(gateway.calls) == 2


@pytest.mark.asyncio
async def test_adapter_sem_readback_verificado_nao_gera_falso_sucesso() -> None:
    service, _, queue = _service(
        gateway=TodoUpsertGateway(readback_verified=False),
        max_attempts=1,
    )
    accepted = await service.criar_todo_evento(_event(event_id="evt-todo-readback-0001"))
    job_id = await queue.consumir()
    await service.processar_job(job_id)
    queue.confirmar()

    result = await service.consultar_job(accepted.job_id)
    assert result.status == JobStatus.DEAD_LETTER
    assert result.last_error == "todo_global_adapter_readback_not_verified"
    assert queue.tamanho_dlq() == 1


@pytest.mark.asyncio
async def test_adapter_ausente_e_fail_closed() -> None:
    service, _, queue = _service(max_attempts=1, adapter_url=None)
    accepted = await service.criar_todo_evento(_event(event_id="evt-todo-no-adapter-0001"))
    job_id = await queue.consumir()
    await service.processar_job(job_id)
    queue.confirmar()

    result = await service.consultar_job(accepted.job_id)
    assert result.status == JobStatus.DEAD_LETTER
    assert result.last_error == "todo_global_adapter_not_configured"


@pytest.mark.asyncio
async def test_falha_persistente_atinge_dlq_no_limite() -> None:
    service, _, queue = _service(gateway=TodoUpsertGateway(fail=True), max_attempts=2)
    accepted = await service.criar_todo_evento(_event(event_id="evt-todo-0004"))

    for _ in range(2):
        job_id = await queue.consumir()
        assert job_id == accepted.job_id
        await service.processar_job(job_id)
        queue.confirmar()

    result = await service.consultar_job(accepted.job_id)
    assert result.status == JobStatus.DEAD_LETTER
    assert result.tentativas == 2
    assert queue.tamanho_dlq() == 1


@pytest.mark.asyncio
async def test_backpressure_no_retry_move_job_para_dlq_sem_perda_silenciosa() -> None:
    service, _, queue = _service(
        gateway=TodoUpsertGateway(fail=True),
        max_queue_size=1,
        max_attempts=3,
    )
    accepted = await service.criar_todo_evento(_event(event_id="evt-todo-retry-pressure-0001"))
    job_id = await queue.consumir()
    await queue.publicar("filler")

    await service.processar_job(job_id)
    queue.confirmar()

    result = await service.consultar_job(accepted.job_id)
    assert result.status == JobStatus.DEAD_LETTER
    assert result.last_error == "retry_queue_capacity_exceeded"
    assert queue.tamanho_dlq() == 1


@pytest.mark.asyncio
async def test_backpressure_rejeita_e_remove_evento_nao_aceito() -> None:
    service, repository, queue = _service(max_queue_size=1)
    first = await service.criar_todo_evento(_event(event_id="evt-todo-0005"))

    with pytest.raises(QueueCapacityError):
        await service.criar_todo_evento(
            _event(
                event_id="evt-todo-0006",
                idempotency_key=_key("ReqSys", "Implementação", "reqsys#outro"),
            )
        )

    jobs = await repository.listar()
    assert queue.tamanho() == 1
    assert len(jobs) == 1
    assert jobs[0].job_id == first.job_id


@pytest.mark.asyncio
async def test_recuperacao_republica_job_persistido_que_ficou_fora_da_fila() -> None:
    service, _, queue = _service()
    accepted = await service.criar_todo_evento(_event(event_id="evt-todo-recover-0001"))
    consumed = await queue.consumir()
    assert consumed == accepted.job_id
    queue.confirmar()
    assert queue.tamanho() == 0

    recovered = await service.recuperar_jobs_pendentes()

    assert recovered == 1
    assert queue.tamanho() == 1


def test_concluido_sem_evidencia_e_criterio_e_rejeitado() -> None:
    with pytest.raises(ValueError, match="CONCLUÍDO exige"):
        _event(event_id="evt-todo-0007", status="CONCLUÍDO")


def test_bloqueado_sem_causa_e_proxima_acao_e_rejeitado() -> None:
    with pytest.raises(ValueError, match="BLOQUEADO exige"):
        _event(event_id="evt-todo-0008", status="BLOQUEADO")


def test_api_publica_evento_com_202_location_e_correlation_id() -> None:
    client = TestClient(app)
    event = _event(event_id="evt-todo-api-0001")

    response = client.post("/api/todo-events", json=event.model_dump(mode="json"))

    assert response.status_code == 202
    assert response.headers["location"] == response.json()["status_url"]
    assert response.headers["x-correlation-id"] == event.correlation_id
    assert response.json()["event_id"] == event.event_id


def test_api_rejeita_reuso_do_event_id_com_payload_diferente_com_409() -> None:
    client = TestClient(app)
    first = _event(event_id="evt-todo-api-conflict-0001")
    second = first.model_copy(deep=True)
    second.todo.status = "EM ANDAMENTO"  # type: ignore[assignment]

    assert client.post("/api/todo-events", json=first.model_dump(mode="json")).status_code == 202
    response = client.post("/api/todo-events", json=second.model_dump(mode="json"))

    assert response.status_code == 409


def test_api_rejeita_conclusao_sem_evidencia_com_422() -> None:
    client = TestClient(app)
    payload = _event(event_id="evt-todo-api-0002").model_dump(mode="json")
    payload["todo"]["status"] = "CONCLUÍDO"
    payload["todo"]["completion_criteria"] = None
    payload["todo"]["evidence"] = None

    response = client.post("/api/todo-events", json=payload)

    assert response.status_code == 422
