from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.core.operational_queue import (
    OperationalTask,
    OperationalTaskType,
    operational_queue,
)
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
    queued = await operational_queue.enqueue(task)
    return ok(
        {
            'schema_version': '1.0.0',
            'accepted': True,
            'task': queued.to_dict(),
        }
    )


@router.post('/worker/run-once')
async def run_operational_worker_once():
    processed = await operational_worker.run_once()
    return ok(
        {
            'schema_version': '1.0.0',
            'processed': processed,
            'worker_running': operational_worker.running,
        }
    )


@router.get('/tasks/{task_id}')
async def get_operational_task(task_id: str):
    task = await operational_queue.get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tarefa operacional não encontrada')
    return ok({'schema_version': '1.0.0', 'task': task.to_dict()})


@router.get('/health')
async def operational_autonomy_health():
    snapshot = await operational_queue.snapshot()
    return ok(
        {
            **snapshot,
            'worker_running': operational_worker.running,
            'runtime_mode': 'in_memory_first_increment',
            'upgrade_path': ['redis_streams', 'rabbitmq', 'azure_service_bus', 'temporal_orchestrator'],
        }
    )
