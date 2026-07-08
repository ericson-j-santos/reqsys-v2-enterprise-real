from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.operational_queue import (
    OperationalTask,
    OperationalTaskType,
    operational_queue,
)

logger = logging.getLogger('reqsys.operational_worker')


async def execute_operational_task(task: OperationalTask) -> dict[str, Any]:
    """Executa uma tarefa operacional com contrato determinístico.

    O primeiro incremento não chama sistemas externos. Ele padroniza o ciclo de vida,
    rastreabilidade e ponto de extensão para adaptadores reais: IA, GitHub, Teams,
    email, Redmine e pipelines de homologação.
    """

    if task.task_type == OperationalTaskType.GENERIC:
        action = task.payload.get('action', 'noop')
    else:
        action = task.task_type.value

    if task.payload.get('force_error') is True:
        raise RuntimeError('erro operacional simulado para validar retry/dlq')

    return {
        'schema_version': '1.0.0',
        'status': 'processed',
        'action': action,
        'correlation_id': task.correlation_id,
        'processed_at': datetime.now(UTC).isoformat(),
    }


class OperationalWorker:
    def __init__(self, poll_interval_seconds: float = 0.25) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name='reqsys-operational-worker')
        logger.info('operational_worker_started')

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info('operational_worker_stopped')

    async def run_once(self) -> bool:
        task = await operational_queue.dequeue()
        if task is None:
            return False
        try:
            result = await execute_operational_task(task)
            await operational_queue.complete(task.task_id, result)
            logger.info('operational_task_completed task_id=%s correlation_id=%s', task.task_id, task.correlation_id)
        except Exception as exc:  # pragma: no cover - caminho exercitado por teste direto do run_once
            await operational_queue.fail(task.task_id, exc)
            logger.exception('operational_task_failed task_id=%s correlation_id=%s', task.task_id, task.correlation_id)
        return True

    async def _run(self) -> None:
        while self._running:
            processed = await self.run_once()
            if not processed:
                await asyncio.sleep(self.poll_interval_seconds)


operational_worker = OperationalWorker()
