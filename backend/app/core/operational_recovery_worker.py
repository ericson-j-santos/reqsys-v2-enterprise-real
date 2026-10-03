from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Sequence

from app.core.operational_queue import (
    OperationalQueueUnavailableError,
    OperationalTask,
    RedisStreamsOperationalQueue,
    operational_queue,
)
from app.core.operational_worker import execute_operational_task

logger = logging.getLogger('reqsys.operational_recovery_worker')


@dataclass(frozen=True, slots=True)
class RecoveryWorkerSettings:
    min_idle_ms: int = 60_000
    batch_size: int = 10
    poll_interval_seconds: float = 5.0

    @classmethod
    def from_environment(cls) -> 'RecoveryWorkerSettings':
        return cls(
            min_idle_ms=_positive_int('OPERATIONAL_QUEUE_CLAIM_MIN_IDLE_MS', 60_000),
            batch_size=_positive_int('OPERATIONAL_QUEUE_CLAIM_BATCH_SIZE', 10),
            poll_interval_seconds=_positive_float('OPERATIONAL_QUEUE_RECOVERY_POLL_SECONDS', 5.0),
        )


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f'{name} deve ser inteiro positivo') from exc
    if value <= 0:
        raise ValueError(f'{name} deve ser maior que zero')
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f'{name} deve ser numérico positivo') from exc
    if value <= 0:
        raise ValueError(f'{name} deve ser maior que zero')
    return value


def _claimed_messages(response: Sequence[Any] | None) -> list[tuple[str, dict[str, str]]]:
    if not response or len(response) < 2:
        return []
    messages = response[1]
    if not isinstance(messages, list):
        return []
    return [(str(message_id), fields) for message_id, fields in messages]


class OperationalRecoveryWorker:
    """Recupera tarefas abandonadas no PEL do Redis Streams.

    O worker usa XAUTOCLAIM para transferir mensagens ociosas ao consumer atual,
    restaura o vínculo task_id -> message_id usado por complete/fail e reutiliza o
    executor operacional existente. Não cria fallback para memória em STG/PROD.
    """

    def __init__(
        self,
        queue: Any = operational_queue,
        settings: RecoveryWorkerSettings | None = None,
    ) -> None:
        self.queue = queue
        self.settings = settings or RecoveryWorkerSettings.from_environment()
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._claim_cursor = '0-0'

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._validate_provider()
        self._running = True
        self._task = asyncio.create_task(self._run(), name='reqsys-operational-recovery-worker')
        logger.info(
            'operational_recovery_worker_started min_idle_ms=%s batch_size=%s',
            self.settings.min_idle_ms,
            self.settings.batch_size,
        )

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
        logger.info('operational_recovery_worker_stopped')

    def _validate_provider(self) -> RedisStreamsOperationalQueue:
        if not isinstance(self.queue, RedisStreamsOperationalQueue):
            raise OperationalQueueUnavailableError(
                'Recovery worker exige OPERATIONAL_QUEUE_PROVIDER=redis_streams'
            )
        return self.queue

    async def run_once(self) -> int:
        queue = self._validate_provider()
        await queue._ensure_group()

        try:
            response = await queue._redis.xautoclaim(
                queue._stream_key,
                queue._consumer_group,
                queue._consumer_name,
                self.settings.min_idle_ms,
                self._claim_cursor,
                count=self.settings.batch_size,
            )
        except Exception as exc:
            raise OperationalQueueUnavailableError(
                f'Falha ao recuperar mensagens abandonadas no Redis Streams: {exc}'
            ) from exc

        if response:
            self._claim_cursor = str(response[0] or '0-0')

        processed = 0
        for message_id, fields in _claimed_messages(response):
            task_id = fields.get('task_id')
            if not task_id:
                await queue._redis.xack(queue._stream_key, queue._consumer_group, message_id)
                logger.error('operational_abandoned_message_invalid message_id=%s', message_id)
                continue

            task = await queue.get(task_id)
            if task is None:
                await queue._redis.xack(queue._stream_key, queue._consumer_group, message_id)
                logger.error(
                    'operational_abandoned_task_missing task_id=%s message_id=%s',
                    task_id,
                    message_id,
                )
                continue

            await queue._redis.hset(queue._processing_key, task_id, message_id)
            await self._process_claimed_task(queue, task)
            processed += 1

        return processed

    async def _process_claimed_task(
        self,
        queue: RedisStreamsOperationalQueue,
        task: OperationalTask,
    ) -> None:
        try:
            result = await execute_operational_task(task)
            await queue.complete(task.task_id, result)
            logger.info(
                'operational_abandoned_task_completed task_id=%s correlation_id=%s',
                task.task_id,
                task.correlation_id,
            )
        except Exception as exc:  # pragma: no cover - validado por integração Redis
            await queue.fail(task.task_id, exc)
            logger.exception(
                'operational_abandoned_task_failed task_id=%s correlation_id=%s',
                task.task_id,
                task.correlation_id,
            )

    async def _run(self) -> None:
        while self._running:
            processed = await self.run_once()
            if processed == 0:
                await asyncio.sleep(self.settings.poll_interval_seconds)


async def _main() -> None:
    worker = OperationalRecoveryWorker()
    worker.start()
    try:
        while worker.running:
            await asyncio.sleep(3600)
    finally:
        await worker.stop()


if __name__ == '__main__':
    asyncio.run(_main())
