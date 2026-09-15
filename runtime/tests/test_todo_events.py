from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.application.services.job_service import JobService
from app.core.config import RuntimeSettings
from app.domain.models.job_assincrono import JobStatus
from app.domain.models.todo_event import TodoEventV1
from app.infrastructure.http.httpx_gateway import HttpxGateway
from app.infrastructure.queue.asyncio_queue import AsyncioQueueGateway
from app.infrastructure.queue.errors import QueueCapacityError
from app.infrastructure.repositories.job_repository_memoria import JobRepositoryMemoria
from app.main import app


class TodoUpsertGateway(HttpxGateway):
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.todos: dict[str, dict] = {}
        self.calls: list[dict] = []

    async def post_json(self, url: str, payload: dict, correlation_id: str) -> dict:
        if self.fail:
            raise RuntimeError("adapter_temporarily_unavailable")
        self.calls.append(payload)
        key = payload["idempotency_key"]
        self.todos[key] = payload["todo"]
        return {
            "upserted": True,
            "idempotency_key": key,
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


def _service(*, gateway: HttpxGateway | None = None, max_queue_size: int = 1000, max_attempts: int = 3):
    repository = JobRepositoryMemoria()
    queue = AsyncioQueueGateway(max_queue_size=max_queue_size)
    settings = RuntimeSettings(
        max_tentativas=max_attempts,
        max_queue_size=max_queue_size,
        retry_backoff_base_seconds=0,
        retry_backoff_max_seconds=0,
        todo_global_adapter_url="https://todo-global.example/upsert",
    )
    service = JobService(repository, queue, gateway or TodoUpsertGateway(), settings)
    return service, repository, queue


@pytest.mark.asyncio
async def test_replay_do_mesmo_event_id_nao_reenfileira() -> None:
    service, _, queue = _service()
    event = _event(event_id="evt-todo-0001")

    first = await service.criar_todo_evento(event)
    second = await service.criar_todo_evento(event)

    assert first.job_id == second.job_id
    assert first.duplicate_event is False
    assert second.duplicate_event is True
    assert queue.tamanho() == 1


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
async def test_falha_persistente_atinge_dlq_no_limite() -> None:
    service, _, queue = _service(gateway=TodoUpsertGateway(fail=True), max_attempts=2)
    accepted = await service.criar_todo_evento(_event(event_id="evt-todo-0004"))

    for _ in range(2):
        job_id = await queue.consumir()
        assert job_id == accepted.job_id
        await service.processar_job(job_id)
        queue.confirmar()

    status = await service.consultar_job(accepted.job_id)
    assert status.status == JobStatus.DEAD_LETTER
    assert status.tentativas == 2
    assert queue.tamanho_dlq() == 1


@pytest.mark.asyncio
async def test_backpressure_rejeita_sem_perder_evento_existente() -> None:
    service, repository, queue = _service(max_queue_size=1)
    first = await service.criar_todo_evento(_event(event_id="evt-todo-0005"))

    with pytest.raises(QueueCapacityError):
        await service.criar_todo_evento(
            _event(
                event_id="evt-todo-0006",
                idempotency_key=_key("ReqSys", "Implementação", "reqsys#outro"),
            )
        )

    assert queue.tamanho() == 1
    assert (await repository.obter(first.job_id)).status == JobStatus.QUEUED


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


def test_api_rejeita_conclusao_sem_evidencia_com_422() -> None:
    client = TestClient(app)
    payload = _event(event_id="evt-todo-api-0002").model_dump(mode="json")
    payload["todo"]["status"] = "CONCLUÍDO"
    payload["todo"]["completion_criteria"] = None
    payload["todo"]["evidence"] = None

    response = client.post("/api/todo-events", json=payload)

    assert response.status_code == 422
