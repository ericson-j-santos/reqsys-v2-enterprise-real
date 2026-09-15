from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import datetime, timezone

import pytest
from redis.asyncio import Redis

from app.application.services.job_service import JobService
from app.core.config import RuntimeSettings
from app.domain.models.job_assincrono import JobStatus
from app.domain.models.todo_event import TodoEventV1
from app.infrastructure.http.httpx_gateway import HttpxGateway
from app.infrastructure.queue.errors import QueueCapacityError
from app.infrastructure.queue.redis_queue import RedisQueueGateway
from app.infrastructure.repositories.job_repository_redis import JobRepositoryRedis

pytestmark = pytest.mark.skipif(
    os.getenv("REQSYS_RUNTIME_REDIS_INTEGRATION") != "1",
    reason="integração Redis habilitada somente no workflow dedicado",
)


class VerifiedTodoGateway(HttpxGateway):
    def __init__(self) -> None:
        self.todos: dict[str, dict] = {}
        self.calls = 0

    async def post_json(self, url: str, payload: dict, correlation_id: str) -> dict:
        self.calls += 1
        key = payload["idempotency_key"]
        effect = "updated" if key in self.todos else "created"
        self.todos[key] = payload["todo"]
        return {
            "todo_id": f"redis-todo-{key[:12]}",
            "idempotency_key": key,
            "effect": effect,
            "canonical_status": payload["todo"]["status"],
            "readback_verified": True,
            "correlation_id": correlation_id,
        }


def _key() -> str:
    return hashlib.sha256(b"reqsys|implementacao|reqsys#1693").hexdigest()


def _event(event_id: str, *, status: str = "PENDENTE") -> TodoEventV1:
    return TodoEventV1.model_validate(
        {
            "schema_version": "1.0",
            "event_id": event_id,
            "event_type": "todo.updated",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "correlation_id": f"corr-{event_id}",
            "idempotency_key": _key(),
            "project": "ReqSys",
            "producer": "redis-integration-test",
            "todo": {
                "title": "Integrar TODO Global com ReqSys",
                "type": "Implementação",
                "external_id": "reqsys#1693",
                "status": status,
                "priority": "P1",
                "e2e_status": "PENDENTE",
                "source": "ReqSys",
            },
        }
    )


async def _redis() -> Redis:
    return Redis.from_url(
        os.getenv("REQSYS_RUNTIME_REDIS_TEST_URL", "redis://localhost:6379/15"),
        decode_responses=True,
    )


def _components(redis: Redis, gateway: VerifiedTodoGateway):
    queue = RedisQueueGateway(
        redis,
        "test:todo:queue",
        "test:todo:processing",
        block_timeout_seconds=1,
        lease_ttl_seconds=5,
        lease_renew_interval_seconds=2,
        max_queue_size=100,
    )
    repository = JobRepositoryRedis(
        redis,
        "test:todo:job",
        "test:todo:job:index",
        ttl_seconds=300,
    )
    settings = RuntimeSettings(
        queue_backend="redis",
        storage_backend="redis",
        max_tentativas=3,
        retry_backoff_base_seconds=0.01,
        retry_backoff_max_seconds=0.05,
        todo_global_adapter_url="https://todo-global.example/upsert",
    )
    return JobService(repository, queue, gateway, settings), repository, queue


@pytest.mark.asyncio
async def test_redis_e2e_persiste_consume_e_replay_nao_duplica_efeito() -> None:
    redis = await _redis()
    await redis.flushdb()
    gateway = VerifiedTodoGateway()
    service, repository, queue = _components(redis, gateway)
    event = _event("evt-redis-e2e-0001")

    try:
        accepted = await asyncio.gather(*(service.criar_todo_evento(event) for _ in range(8)))
        assert len({item.job_id for item in accepted}) == 1
        assert sum(item.duplicate_event for item in accepted) == 7
        persisted = await repository.obter(accepted[0].job_id)
        assert persisted.status == JobStatus.QUEUED

        while await queue.tamanho() > 0:
            job_id = await queue.consumir()
            await service.processar_job(job_id)
            await queue.confirmar()

        completed = await repository.obter(accepted[0].job_id)
        assert completed.status == JobStatus.COMPLETED
        assert gateway.calls == 1
        assert len(gateway.todos) == 1

        replay = await service.criar_todo_evento(event)
        assert replay.duplicate_event is True
        assert replay.status == JobStatus.COMPLETED.value
        assert await queue.tamanho() == 0
        assert gateway.calls == 1

        update = await service.criar_todo_evento(_event("evt-redis-e2e-0002", status="EM ANDAMENTO"))
        job_id = await queue.consumir()
        assert job_id == update.job_id
        await service.processar_job(job_id)
        await queue.confirmar()

        assert len(gateway.todos) == 1
        assert gateway.todos[_key()]["status"] == "EM ANDAMENTO"
        assert gateway.calls == 2
    finally:
        await redis.flushdb()
        await redis.aclose()


@pytest.mark.asyncio
async def test_redis_fila_atrasada_backpressure_e_dlq_sao_reais() -> None:
    redis = await _redis()
    await redis.flushdb()
    queue = RedisQueueGateway(
        redis,
        "test:delivery:queue",
        "test:delivery:processing",
        block_timeout_seconds=1,
        lease_ttl_seconds=5,
        lease_renew_interval_seconds=2,
        max_queue_size=2,
    )

    try:
        await queue.publicar("immediate")
        await queue.publicar("delayed", delay_seconds=0.01)
        assert await queue.tamanho() == 2

        with pytest.raises(QueueCapacityError):
            await queue.publicar("rejected")

        await asyncio.sleep(0.02)
        assert await queue.promover_atrasados() == 1
        assert await queue.tamanho() == 2

        consumed = await queue.consumir()
        assert consumed == "immediate"
        await queue.confirmar()

        await queue.quarentenar("manual-dlq-control")
        assert await queue.tamanho_dlq() == 1
    finally:
        await redis.flushdb()
        await redis.aclose()
