import pytest

from app.core.operational_queue import (
    OperationalQueue,
    OperationalTask,
    OperationalTaskStatus,
    OperationalTaskType,
)


@pytest.mark.asyncio
async def test_enqueue_dequeue_and_complete_task():
    queue = OperationalQueue()
    task = OperationalTask(
        task_type=OperationalTaskType.GENERIC,
        payload={'action': 'smoke'},
        correlation_id='corr-001',
    )

    queued = await queue.enqueue(task)
    dequeued = await queue.dequeue()
    assert queued.task_id == dequeued.task_id
    assert dequeued.status == OperationalTaskStatus.RUNNING
    assert dequeued.attempts == 1

    await queue.complete(dequeued.task_id, {'status': 'ok'})
    stored = await queue.get(dequeued.task_id)
    assert stored.status == OperationalTaskStatus.COMPLETED
    assert stored.result == {'status': 'ok'}


@pytest.mark.asyncio
async def test_idempotency_key_returns_existing_task():
    queue = OperationalQueue()
    first = OperationalTask(
        task_type=OperationalTaskType.GENERIC,
        payload={'action': 'first'},
        correlation_id='corr-001',
        idempotency_key='same-key',
    )
    second = OperationalTask(
        task_type=OperationalTaskType.GENERIC,
        payload={'action': 'second'},
        correlation_id='corr-002',
        idempotency_key='same-key',
    )

    queued_first = await queue.enqueue(first)
    queued_second = await queue.enqueue(second)

    assert queued_first.task_id == queued_second.task_id
    snapshot = await queue.snapshot()
    assert snapshot['total_tasks'] == 1
    assert snapshot['queued_items'] == 1


@pytest.mark.asyncio
async def test_fail_retries_and_then_dead_letter():
    queue = OperationalQueue()
    task = OperationalTask(
        task_type=OperationalTaskType.GENERIC,
        payload={'force_error': True},
        correlation_id='corr-001',
        max_attempts=2,
    )

    await queue.enqueue(task)
    first = await queue.dequeue()
    await queue.fail(first.task_id, 'erro 1')
    assert (await queue.get(first.task_id)).status == OperationalTaskStatus.PENDING

    second = await queue.dequeue()
    await queue.fail(second.task_id, 'erro 2')
    stored = await queue.get(second.task_id)
    assert stored.status == OperationalTaskStatus.DEAD_LETTER
    assert stored.last_error == 'erro 2'
