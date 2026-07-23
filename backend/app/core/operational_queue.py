from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Deque, Dict, Optional, Protocol

from app.core.config import settings

logger = logging.getLogger('reqsys.operational_queue')


class OperationalQueueUnavailableError(RuntimeError):
    """Indica que o provider configurado não está disponível."""


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
    next_attempt_at: Optional[datetime] = None
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
            'next_attempt_at': self.next_attempt_at.isoformat() if self.next_attempt_at else None,
            'last_error': self.last_error,
            'result': self.result,
        }

    def serialize(self) -> str:
        payload = asdict(self)
        payload['task_type'] = self.task_type.value
        payload['status'] = self.status.value
        for name in ('created_at', 'updated_at', 'next_attempt_at'):
            value = payload[name]
            payload[name] = value.isoformat() if value else None
        return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))

    @classmethod
    def deserialize(cls, value: str | bytes) -> OperationalTask:
        payload = json.loads(value)
        payload['task_type'] = OperationalTaskType(payload['task_type'])
        payload['status'] = OperationalTaskStatus(payload['status'])
        for name in ('created_at', 'updated_at', 'next_attempt_at'):
            if payload.get(name):
                payload[name] = datetime.fromisoformat(payload[name])
        return cls(**payload)


class OperationalQueueProvider(Protocol):
    provider_name: str
    durable: bool

    async def enqueue(self, task: OperationalTask) -> OperationalTask:
        raise NotImplementedError

    async def dequeue(self) -> Optional[OperationalTask]:
        raise NotImplementedError

    async def complete(self, task_id: str, result: dict[str, Any]) -> None:
        raise NotImplementedError

    async def fail(self, task_id: str, error: Exception | str) -> None:
        raise NotImplementedError

    async def get(self, task_id: str) -> Optional[OperationalTask]:
        raise NotImplementedError

    async def snapshot(self) -> dict[str, Any]:
        raise NotImplementedError


def _retry_delay_seconds(base_seconds: float, attempts: int) -> float:
    return max(0.0, base_seconds) * (2 ** max(0, attempts - 1))


class OperationalQueue:
    """Provider em memória, permitido somente para DEV e testes."""

    provider_name = 'memory'
    durable = False

    def __init__(self, retry_base_seconds: float = 0.0) -> None:
        self._queue: Deque[str] = deque()
        self._tasks: Dict[str, OperationalTask] = {}
        self._idempotency_index: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._retry_base_seconds = retry_base_seconds

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
                'operational_task_enqueued provider=%s task_id=%s type=%s correlation_id=%s',
                self.provider_name,
                task.task_id,
                task.task_type.value,
                task.correlation_id,
            )
            return task

    async def dequeue(self) -> Optional[OperationalTask]:
        async with self._lock:
            now = datetime.now(UTC)
            queue_size = len(self._queue)
            for _ in range(queue_size):
                task_id = self._queue.popleft()
                task = self._tasks.get(task_id)
                if task and task.status == OperationalTaskStatus.PENDING:
                    if task.next_attempt_at and task.next_attempt_at > now:
                        self._queue.append(task_id)
                        continue
                    task.status = OperationalTaskStatus.RUNNING
                    task.attempts += 1
                    task.next_attempt_at = None
                    task.updated_at = now
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
                logger.error('operational_task_dead_letter provider=%s task_id=%s error=%s', self.provider_name, task_id, error)
                return
            delay = _retry_delay_seconds(self._retry_base_seconds, task.attempts)
            task.status = OperationalTaskStatus.PENDING
            task.next_attempt_at = task.updated_at + timedelta(seconds=delay)
            self._queue.append(task_id)
            logger.warning(
                'operational_task_retry_scheduled provider=%s task_id=%s attempt=%s delay_seconds=%s',
                self.provider_name,
                task_id,
                task.attempts,
                delay,
            )

    async def get(self, task_id: str) -> Optional[OperationalTask]:
        async with self._lock:
            return self._tasks.get(task_id)

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            totals = {status.value: 0 for status in OperationalTaskStatus}
            for task in self._tasks.values():
                totals[task.status.value] += 1
            pending_created = [
                task.created_at
                for task in self._tasks.values()
                if task.status == OperationalTaskStatus.PENDING
            ]
            oldest_age = (
                max(0.0, (datetime.now(UTC) - min(pending_created)).total_seconds())
                if pending_created
                else None
            )
            return _snapshot_payload(
                provider=self.provider_name,
                connected=True,
                durable=self.durable,
                queued_items=len(self._queue),
                processing_items=totals[OperationalTaskStatus.RUNNING.value],
                dlq_items=totals[OperationalTaskStatus.DEAD_LETTER.value],
                total_tasks=len(self._tasks),
                totals=totals,
                oldest_message_age_seconds=oldest_age,
            )


class RedisStreamsOperationalQueue:
    """Provider durável baseado em Redis Streams, consumer group e DLQ."""

    provider_name = 'redis_streams'
    durable = True

    def __init__(
        self,
        redis: Any,
        *,
        key_prefix: str = 'reqsys:operational',
        consumer_group: str = 'reqsys-operational-workers',
        consumer_name: Optional[str] = None,
        retry_base_seconds: float = 1.0,
    ) -> None:
        self._redis = redis
        self._stream_key = f'{key_prefix}:stream'
        self._dlq_key = f'{key_prefix}:dlq'
        self._retry_key = f'{key_prefix}:retry'
        self._task_prefix = f'{key_prefix}:task'
        self._task_index = f'{key_prefix}:tasks'
        self._idempotency_prefix = f'{key_prefix}:idempotency'
        self._processing_key = f'{key_prefix}:processing'
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name or f'reqsys-{uuid.uuid4().hex[:12]}'
        self._retry_base_seconds = retry_base_seconds
        self._group_ready = False
        self._group_lock = asyncio.Lock()

    def _task_key(self, task_id: str) -> str:
        return f'{self._task_prefix}:{task_id}'

    def _idempotency_key(self, value: str) -> str:
        digest = hashlib.sha256(value.encode('utf-8')).hexdigest()
        return f'{self._idempotency_prefix}:{digest}'

    async def _ensure_group(self) -> None:
        if self._group_ready:
            return
        async with self._group_lock:
            if self._group_ready:
                return
            try:
                await self._redis.ping()
                try:
                    await self._redis.xgroup_create(
                        self._stream_key,
                        self._consumer_group,
                        id='0',
                        mkstream=True,
                    )
                except Exception as exc:
                    if 'BUSYGROUP' not in str(exc):
                        raise
            except Exception as exc:
                raise OperationalQueueUnavailableError(f'Redis Streams indisponível: {exc}') from exc
            self._group_ready = True

    async def enqueue(self, task: OperationalTask) -> OperationalTask:
        await self._ensure_group()
        try:
            if task.idempotency_key:
                idempotency_key = self._idempotency_key(task.idempotency_key)
                acquired = await self._redis.set(idempotency_key, task.task_id, nx=True)
                if not acquired:
                    existing_id = await self._redis.get(idempotency_key)
                    existing = await self.get(existing_id)
                    if existing is not None:
                        return existing
                    raise OperationalQueueUnavailableError('Índice de idempotência inconsistente no Redis')

            async with self._redis.pipeline(transaction=True) as pipeline:
                pipeline.set(self._task_key(task.task_id), task.serialize())
                pipeline.sadd(self._task_index, task.task_id)
                pipeline.xadd(self._stream_key, {'task_id': task.task_id})
                await pipeline.execute()
            logger.info(
                'operational_task_enqueued provider=%s task_id=%s type=%s correlation_id=%s',
                self.provider_name,
                task.task_id,
                task.task_type.value,
                task.correlation_id,
            )
            return task
        except OperationalQueueUnavailableError:
            raise
        except Exception as exc:
            raise OperationalQueueUnavailableError(f'Falha ao enfileirar no Redis Streams: {exc}') from exc

    async def _promote_due_retries(self) -> None:
        now = datetime.now(UTC).timestamp()
        task_ids = await self._redis.zrangebyscore(self._retry_key, '-inf', now, start=0, num=100)
        for task_id in task_ids:
            removed = await self._redis.zrem(self._retry_key, task_id)
            if removed:
                await self._redis.xadd(self._stream_key, {'task_id': task_id})

    async def dequeue(self) -> Optional[OperationalTask]:
        await self._ensure_group()
        try:
            await self._promote_due_retries()
            response = await self._redis.xreadgroup(
                self._consumer_group,
                self._consumer_name,
                {self._stream_key: '>'},
                count=1,
                block=1,
            )
            if not response:
                return None
            _, messages = response[0]
            message_id, fields = messages[0]
            task_id = fields['task_id']
            task = await self.get(task_id)
            if task is None:
                await self._redis.xack(self._stream_key, self._consumer_group, message_id)
                return None

            task.status = OperationalTaskStatus.RUNNING
            task.attempts += 1
            task.next_attempt_at = None
            task.updated_at = datetime.now(UTC)
            async with self._redis.pipeline(transaction=True) as pipeline:
                pipeline.set(self._task_key(task_id), task.serialize())
                pipeline.hset(self._processing_key, task_id, message_id)
                await pipeline.execute()
            return task
        except OperationalQueueUnavailableError:
            raise
        except Exception as exc:
            raise OperationalQueueUnavailableError(f'Falha ao consumir Redis Streams: {exc}') from exc

    async def _message_id(self, task_id: str) -> Optional[str]:
        return await self._redis.hget(self._processing_key, task_id)

    async def complete(self, task_id: str, result: dict[str, Any]) -> None:
        task = await self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        task.status = OperationalTaskStatus.COMPLETED
        task.result = result
        task.updated_at = datetime.now(UTC)
        message_id = await self._message_id(task_id)
        try:
            async with self._redis.pipeline(transaction=True) as pipeline:
                pipeline.set(self._task_key(task_id), task.serialize())
                if message_id:
                    pipeline.xack(self._stream_key, self._consumer_group, message_id)
                pipeline.hdel(self._processing_key, task_id)
                await pipeline.execute()
        except Exception as exc:
            raise OperationalQueueUnavailableError(f'Falha ao confirmar tarefa no Redis Streams: {exc}') from exc

    async def fail(self, task_id: str, error: Exception | str) -> None:
        task = await self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        task.last_error = str(error)
        task.updated_at = datetime.now(UTC)
        message_id = await self._message_id(task_id)

        try:
            async with self._redis.pipeline(transaction=True) as pipeline:
                if task.attempts >= task.max_attempts:
                    task.status = OperationalTaskStatus.DEAD_LETTER
                    task.next_attempt_at = None
                    pipeline.xadd(
                        self._dlq_key,
                        {
                            'task_id': task_id,
                            'correlation_id': task.correlation_id,
                            'attempts': str(task.attempts),
                            'failed_at': task.updated_at.isoformat(),
                            'error': task.last_error,
                        },
                    )
                else:
                    delay = _retry_delay_seconds(self._retry_base_seconds, task.attempts)
                    task.status = OperationalTaskStatus.PENDING
                    task.next_attempt_at = task.updated_at + timedelta(seconds=delay)
                    pipeline.zadd(self._retry_key, {task_id: task.next_attempt_at.timestamp()})
                pipeline.set(self._task_key(task_id), task.serialize())
                if message_id:
                    pipeline.xack(self._stream_key, self._consumer_group, message_id)
                pipeline.hdel(self._processing_key, task_id)
                await pipeline.execute()
        except Exception as exc:
            raise OperationalQueueUnavailableError(f'Falha ao registrar retry/DLQ no Redis Streams: {exc}') from exc

    async def get(self, task_id: str) -> Optional[OperationalTask]:
        if not task_id:
            return None
        try:
            payload = await self._redis.get(self._task_key(task_id))
            return OperationalTask.deserialize(payload) if payload else None
        except Exception as exc:
            raise OperationalQueueUnavailableError(f'Falha ao consultar tarefa no Redis: {exc}') from exc

    async def snapshot(self) -> dict[str, Any]:
        try:
            await self._ensure_group()
            task_ids = await self._redis.smembers(self._task_index)
            tasks: list[OperationalTask] = []
            for task_id in task_ids:
                task = await self.get(task_id)
                if task is not None:
                    tasks.append(task)
            totals = {status.value: 0 for status in OperationalTaskStatus}
            for task in tasks:
                totals[task.status.value] += 1
            pending_created = [
                task.created_at
                for task in tasks
                if task.status == OperationalTaskStatus.PENDING
            ]
            oldest_age = (
                max(0.0, (datetime.now(UTC) - min(pending_created)).total_seconds())
                if pending_created
                else None
            )
            groups = await self._redis.xinfo_groups(self._stream_key)
            group = next(
                (item for item in groups if item.get('name') == self._consumer_group),
                {},
            )
            queued = int(group.get('lag') or 0) + int(await self._redis.zcard(self._retry_key))
            processing = int(await self._redis.hlen(self._processing_key))
            dlq = int(await self._redis.xlen(self._dlq_key))
            return _snapshot_payload(
                provider=self.provider_name,
                connected=True,
                durable=self.durable,
                queued_items=queued,
                processing_items=processing,
                dlq_items=dlq,
                total_tasks=len(tasks),
                totals=totals,
                oldest_message_age_seconds=oldest_age,
            )
        except OperationalQueueUnavailableError as exc:
            return _unavailable_snapshot(self.provider_name, str(exc))
        except Exception as exc:
            return _unavailable_snapshot(self.provider_name, f'Redis Streams indisponível: {exc}')


class UnavailableOperationalQueue:
    durable = True

    def __init__(self, provider_name: str, reason: str) -> None:
        self.provider_name = provider_name
        self.reason = reason

    async def _raise(self) -> None:
        raise OperationalQueueUnavailableError(self.reason)

    async def enqueue(self, task: OperationalTask) -> OperationalTask:
        await self._raise()
        return task

    async def dequeue(self) -> Optional[OperationalTask]:
        await self._raise()
        return None

    async def complete(self, task_id: str, result: dict[str, Any]) -> None:
        await self._raise()

    async def fail(self, task_id: str, error: Exception | str) -> None:
        await self._raise()

    async def get(self, task_id: str) -> Optional[OperationalTask]:
        await self._raise()
        return None

    async def snapshot(self) -> dict[str, Any]:
        return _unavailable_snapshot(self.provider_name, self.reason)


def _snapshot_payload(
    *,
    provider: str,
    connected: bool,
    durable: bool,
    queued_items: int,
    processing_items: int,
    dlq_items: int,
    total_tasks: int,
    totals: dict[str, int],
    oldest_message_age_seconds: Optional[float],
) -> dict[str, Any]:
    return {
        'schema_version': '2.0.0',
        'component': 'operational_queue',
        'provider': provider,
        'connected': connected,
        'durable': durable,
        'queued_items': queued_items,
        'processing_items': processing_items,
        'dlq_items': dlq_items,
        'oldest_message_age_seconds': oldest_message_age_seconds,
        'total_tasks': total_tasks,
        'totals_by_status': totals,
        'timestamp': datetime.now(UTC).isoformat(),
    }


def _unavailable_snapshot(provider: str, reason: str) -> dict[str, Any]:
    return {
        **_snapshot_payload(
            provider=provider,
            connected=False,
            durable=True,
            queued_items=0,
            processing_items=0,
            dlq_items=0,
            total_tasks=0,
            totals={status.value: 0 for status in OperationalTaskStatus},
            oldest_message_age_seconds=None,
        ),
        'error': reason,
    }


def build_operational_queue() -> OperationalQueueProvider:
    environment = settings.normalized_environment
    configured_provider = settings.operational_queue_provider.strip().lower()
    redis_required = environment in {'homologacao', 'producao'}
    provider = configured_provider or ('redis_streams' if redis_required else 'memory')

    if provider == 'memory':
        if redis_required:
            return UnavailableOperationalQueue(
                'redis_streams',
                'OPERATIONAL_QUEUE_PROVIDER=memory não é permitido em STG/PROD',
            )
        return OperationalQueue(retry_base_seconds=settings.operational_queue_retry_base_seconds)

    if provider not in {'redis', 'redis_streams'}:
        return UnavailableOperationalQueue(provider, f'Provider de fila não suportado: {provider}')
    if not settings.operational_queue_redis_url.strip():
        return UnavailableOperationalQueue(
            'redis_streams',
            'OPERATIONAL_QUEUE_REDIS_URL ou REDIS_URL é obrigatório para Redis Streams',
        )

    try:
        from redis.asyncio import Redis

        redis = Redis.from_url(
            settings.operational_queue_redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.operational_queue_connect_timeout_seconds,
            socket_timeout=settings.operational_queue_connect_timeout_seconds,
        )
    except Exception as exc:
        return UnavailableOperationalQueue('redis_streams', f'Falha ao inicializar Redis Streams: {exc}')

    return RedisStreamsOperationalQueue(
        redis,
        key_prefix=settings.operational_queue_key_prefix,
        consumer_group=settings.operational_queue_consumer_group,
        retry_base_seconds=settings.operational_queue_retry_base_seconds,
    )


operational_queue = build_operational_queue()
