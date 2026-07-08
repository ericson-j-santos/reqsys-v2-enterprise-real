from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Deque, Dict, Optional

logger = logging.getLogger('reqsys.operational_queue')


class OperationalTaskStatus(StrEnum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    DEAD_LETTER = 'dead_letter'


class OperationalTaskType(StrEnum):
    REQUIREMENT_ANALYSIS = 'requirement_analysis'
    BDD_GENERATION = 'bdd_generation'
    QA_VALIDATION = 'qa_validation'
    GITHUB_AUTOMATION = 'github_automation'
    TEAMS_NOTIFICATION = 'teams_notification'
    EMAIL_REPORT = 'email_report'
    GENERIC = 'generic'


@dataclass(slots=True)
class OperationalTask:
    task_type: OperationalTaskType
    payload: dict[str, Any]
    correlation_id: str
    idempotency_key: Optional[str] = None
    max_attempts: int = 3
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: OperationalTaskStatus = OperationalTaskStatus.PENDING
    attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_error: Optional[str] = None
    result: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'task_type': self.task_type.value,
            'status': self.status.value,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'correlation_id': self.correlation_id,
            'idempotency_key': self.idempotency_key,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_error': self.last_error,
            'result': self.result,
        }


class OperationalQueue:
    """Fila operacional local para evolução segura rumo a runtime autônomo.

    Esta implementação é propositalmente autocontida para não exigir Redis/RabbitMQ
    no primeiro incremento. O contrato público permite trocar o backend da fila sem
    alterar os consumidores da API.
    """

    def __init__(self) -> None:
        self._queue: Deque[str] = deque()
        self._tasks: Dict[str, OperationalTask] = {}
        self._idempotency_index: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, task: OperationalTask) -> OperationalTask:
        async with self._lock:
            if task.idempotency_key and task.idempotency_key in self._idempotency_index:
                existing_id = self._idempotency_index[task.idempotency_key]
                return self._tasks[existing_id]

            self._tasks[task.task_id] = task
            if task.idempotency_key:
                self._idempotency_index[task.idempotency_key] = task.task_id
            self._queue.append(task.task_id)
            logger.info(
                'operational_task_enqueued task_id=%s type=%s correlation_id=%s',
                task.task_id,
                task.task_type.value,
                task.correlation_id,
            )
            return task

    async def dequeue(self) -> Optional[OperationalTask]:
        async with self._lock:
            while self._queue:
                task_id = self._queue.popleft()
                task = self._tasks.get(task_id)
                if task and task.status == OperationalTaskStatus.PENDING:
                    task.status = OperationalTaskStatus.RUNNING
                    task.attempts += 1
                    task.updated_at = datetime.now(UTC)
                    return task
            return None

    async def complete(self, task_id: str, result: dict[str, Any]) -> None:
        async with self._lock:
            task = self._tasks[task_id]
            task.status = OperationalTaskStatus.COMPLETED
            task.result = result
            task.updated_at = datetime.now(UTC)

    async def fail(self, task_id: str, error: Exception | str) -> None:
        async with self._lock:
            task = self._tasks[task_id]
            task.last_error = str(error)
            task.updated_at = datetime.now(UTC)
            if task.attempts >= task.max_attempts:
                task.status = OperationalTaskStatus.DEAD_LETTER
                logger.error('operational_task_dead_letter task_id=%s error=%s', task_id, error)
                return
            task.status = OperationalTaskStatus.PENDING
            self._queue.append(task_id)
            logger.warning('operational_task_retry_scheduled task_id=%s attempt=%s', task_id, task.attempts)

    async def get(self, task_id: str) -> Optional[OperationalTask]:
        async with self._lock:
            return self._tasks.get(task_id)

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            totals = {status.value: 0 for status in OperationalTaskStatus}
            for task in self._tasks.values():
                totals[task.status.value] += 1
            return {
                'schema_version': '1.0.0',
                'component': 'operational_queue',
                'queued_items': len(self._queue),
                'total_tasks': len(self._tasks),
                'totals_by_status': totals,
                'timestamp': datetime.now(UTC).isoformat(),
            }


operational_queue = OperationalQueue()
