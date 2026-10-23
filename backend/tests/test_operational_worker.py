from uuid import uuid4

import pytest

from app.core.operational_queue import (
    OperationalTask,
    OperationalTaskStatus,
    OperationalTaskType,
    operational_queue,
)
from app.core.operational_worker import operational_worker


@pytest.mark.asyncio
async def test_worker_run_once_processes_generic_task():
    run_id = uuid4().hex
    task = OperationalTask(
        task_type=OperationalTaskType.GENERIC,
        payload={'action': 'validar-runtime'},
        correlation_id=f'corr-worker-{run_id}',
        idempotency_key=f'test-worker-run-once-processes-generic-task-{run_id}',
    )

    queued = await operational_queue.enqueue(task)
    processed = await operational_worker.run_once()

    stored = await operational_queue.get(queued.task_id)
    assert processed is True
    assert stored.status == OperationalTaskStatus.COMPLETED
    assert stored.result['action'] == 'validar-runtime'
    assert stored.result['correlation_id'] == f'corr-worker-{run_id}'


@pytest.mark.asyncio
async def test_worker_run_once_returns_false_when_queue_is_empty():
    processed = await operational_worker.run_once()
    assert processed is False

