from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.core.operational_queue import (
    OperationalQueueUnavailableError,
    OperationalTask,
    OperationalTaskType,
    operational_queue,
)
from app.core.operational_queue_observability import OperationalQueueObserver
from app.core.operational_queue_readiness import OperationalQueueReadinessPolicy
from app.core.operational_worker import operational_worker

router = APIRouter(prefix='/api/operational-autonomy', tags=['operational-autonomy'])


class EnqueueOperationalTaskRequest(BaseModel):
    task_type: OperationalTaskType = Field(default=OperationalTaskType.GENERIC)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=180)
    max_attempts: int = Field(default=3, ge=1, le=10)


def _correlation_id_from_request(request: Request) -> str:
    return request.headers.get('X-Correlation-Id') or request.headers.get('X-Request-ID') or 'reqsys-api'


@router.post('/tasks', status_code=status.HTTP_202_ACCEPTED)
async def enqueue_operational_task(body: EnqueueOperationalTaskRequest, request: Request):
    task = OperationalTask(
        task_type=body.task_type,
        payload=body.payload,
        correlation_id=_correlation_id_from_request(request),
        idempotency_key=body.idempotency_key,
        max_attempts=body.max_attempts,
    )
    try:
        queued = await operational_queue.enqueue(task)
    except OperationalQueueUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return ok(
        {
            'schema_version': '1.0.0',
            'accepted': True,
            'task': queued.to_dict(),
        }
    )


@router.post('/worker/run-once')
async def run_operational_worker_once():
    try:
        processed = await operational_worker.run_once()
    except OperationalQueueUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return ok(
        {
            'schema_version': '1.0.0',
            'processed': processed,
            'worker_running': operational_worker.running,
        }
    )


@router.get('/tasks/{task_id}')
async def get_operational_task(task_id: str):
    try:
        task = await operational_queue.get(task_id)
    except OperationalQueueUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tarefa operacional não encontrada')
    return ok({'schema_version': '1.0.0', 'task': task.to_dict()})


@router.get('/queue/consumers')
async def operational_queue_consumers():
    """Expõe evidência detalhada do consumer group Redis Streams."""

    try:
        snapshot = await OperationalQueueObserver().snapshot()
    except OperationalQueueUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return ok(snapshot)


@router.get('/queue/readiness')
async def operational_queue_readiness():
    """Avalia SLOs da fila e retorna 503 somente quando ela não está pronta."""

    try:
        snapshot = await OperationalQueueObserver().snapshot()
        readiness = OperationalQueueReadinessPolicy.from_environment().evaluate(snapshot)
    except (OperationalQueueUnavailableError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    payload = ok(readiness)
    if readiness['ready']:
        return payload
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)


@router.get('/health')
async def operational_autonomy_health():
    snapshot = await operational_queue.snapshot()
    consumer_observability: dict[str, Any] | None = None
    queue_readiness: dict[str, Any] | None = None

    if snapshot.get('provider') == 'redis_streams' and snapshot.get('connected') is True:
        try:
            consumer_observability = await OperationalQueueObserver().snapshot()
            queue_readiness = OperationalQueueReadinessPolicy.from_environment().evaluate(
                consumer_observability
            )
        except (OperationalQueueUnavailableError, ValueError) as exc:
            consumer_observability = {
                'schema_version': '1.0.0',
                'component': 'operational_queue_consumers',
                'status': 'critical',
                'reasons': ['observability_unavailable'],
                'error': str(exc),
            }
            queue_readiness = {
                'schema_version': '1.0.0',
                'component': 'operational_queue_readiness',
                'ready': False,
                'status': 'not_ready',
                'reasons': ['observability_unavailable'],
            }

    return ok(
        {
            **snapshot,
            'worker_running': operational_worker.running,
            'runtime_mode': snapshot['provider'],
            'consumer_observability': consumer_observability,
            'queue_readiness': queue_readiness,
            'upgrade_path': ['rabbitmq', 'azure_service_bus', 'temporal_orchestrator'],
        }
    )
