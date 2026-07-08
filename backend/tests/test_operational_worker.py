import asyncio

from app.core.operational_queue import OperationalTask, OperationalTaskStatus, OperationalTaskType, operational_queue
from app.core.operational_worker import operational_worker


def test_worker_run_once_processes_generic_task():
    async def scenario():
        task = OperationalTask(
            task_type=OperationalTaskType.GENERIC,
            payload={'action': 'validar-runtime'},
            correlation_id='corr-worker-001',
            idempotency_key='test-worker-run-once-processes-generic-task',
        )

        queued = await operational_queue.enqueue(task)
        processed = await operational_worker.run_once()

        stored = await operational_queue.get(queued.task_id)
        assert processed is True
        assert stored.status == OperationalTaskStatus.COMPLETED
        assert stored.result['action'] == 'validar-runtime'
        assert stored.result['correlation_id'] == 'corr-worker-001'

    asyncio.run(scenario())


def test_worker_run_once_returns_false_when_queue_is_empty():
    async def scenario():
        processed = await operational_worker.run_once()
        assert processed is False

    asyncio.run(scenario())
