from __future__ import annotations

from typing import Any

import pytest

from app.core.config import settings
from app.core.operational_queue import (
    OperationalQueue,
    OperationalQueueUnavailableError,
    OperationalTask,
    OperationalTaskStatus,
    OperationalTaskType,
    RedisStreamsOperationalQueue,
    UnavailableOperationalQueue,
    build_operational_queue,
)


class FakePipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self.redis = redis
        self.commands: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def __aenter__(self) -> FakePipeline:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def __getattr__(self, name: str):
        def queue_command(*args: Any, **kwargs: Any) -> FakePipeline:
            self.commands.append((name, args, kwargs))
            return self

        return queue_command

    async def execute(self) -> list[Any]:
        results = []
        for name, args, kwargs in self.commands:
            results.append(await getattr(self.redis, name)(*args, **kwargs))
        return results


class FakeRedis:
    """Double funcional mínimo para validar o contrato Redis Streams."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.stream_offsets: dict[tuple[str, str], int] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}
        self.groups: set[tuple[str, str]] = set()
        self.sequence = 0

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        assert transaction is True
        return FakePipeline(self)

    async def ping(self) -> bool:
        return True

    async def xgroup_create(self, stream: str, group: str, id: str, mkstream: bool) -> bool:
        assert id == '0'
        assert mkstream is True
        key = (stream, group)
        if key in self.groups:
            raise RuntimeError('BUSYGROUP Consumer Group name already exists')
        self.groups.add(key)
        self.streams.setdefault(stream, [])
        return True

    async def set(self, key: str, value: str, nx: bool = False) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def sadd(self, key: str, value: str) -> int:
        target = self.sets.setdefault(key, set())
        previous = len(target)
        target.add(value)
        return int(len(target) > previous)

    async def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    async def xadd(self, key: str, fields: dict[str, str]) -> str:
        self.sequence += 1
        message_id = f'{self.sequence}-0'
        self.streams.setdefault(key, []).append((message_id, fields))
        return message_id

    async def xreadgroup(
        self,
        group: str,
        consumer: str,
        streams: dict[str, str],
        count: int,
        block: int,
    ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
        assert consumer
        assert count == 1
        assert block == 1
        stream = next(iter(streams))
        offset_key = (stream, group)
        offset = self.stream_offsets.get(offset_key, 0)
        messages = self.streams.get(stream, [])
        if offset >= len(messages):
            return []
        self.stream_offsets[offset_key] = offset + 1
        return [(stream, [messages[offset]])]

    async def xack(self, stream: str, group: str, message_id: str) -> int:
        assert (stream, group) in self.groups
        assert message_id
        return 1

    async def hset(self, key: str, field: str, value: str) -> int:
        self.hashes.setdefault(key, {})[field] = value
        return 1

    async def hget(self, key: str, field: str) -> str | None:
        return self.hashes.get(key, {}).get(field)

    async def hdel(self, key: str, field: str) -> int:
        return int(self.hashes.get(key, {}).pop(field, None) is not None)

    async def hlen(self, key: str) -> int:
        return len(self.hashes.get(key, {}))

    async def zadd(self, key: str, values: dict[str, float]) -> int:
        self.sorted_sets.setdefault(key, {}).update(values)
        return len(values)

    async def zrangebyscore(
        self,
        key: str,
        minimum: str,
        maximum: float,
        *,
        start: int,
        num: int,
    ) -> list[str]:
        assert minimum == '-inf'
        due = [
            member
            for member, score in sorted(self.sorted_sets.get(key, {}).items(), key=lambda item: item[1])
            if score <= maximum
        ]
        return due[start:start + num]

    async def zrem(self, key: str, member: str) -> int:
        return int(self.sorted_sets.get(key, {}).pop(member, None) is not None)

    async def zcard(self, key: str) -> int:
        return len(self.sorted_sets.get(key, {}))

    async def xlen(self, key: str) -> int:
        return len(self.streams.get(key, []))

    async def xinfo_groups(self, key: str) -> list[dict[str, Any]]:
        group = next(group for stream, group in self.groups if stream == key)
        delivered = self.stream_offsets.get((key, group), 0)
        return [{'name': group, 'lag': len(self.streams.get(key, [])) - delivered}]


@pytest.mark.asyncio
async def test_redis_streams_preserves_idempotency_retry_and_dlq():
    queue = RedisStreamsOperationalQueue(FakeRedis(), retry_base_seconds=0)
    first = OperationalTask(
        task_type=OperationalTaskType.GENERIC,
        payload={'force_error': True},
        correlation_id='corr-redis-001',
        idempotency_key='redis-same-key',
        max_attempts=2,
    )
    duplicate = OperationalTask(
        task_type=OperationalTaskType.GENERIC,
        payload={'action': 'duplicate'},
        correlation_id='corr-redis-002',
        idempotency_key='redis-same-key',
    )

    queued = await queue.enqueue(first)
    assert (await queue.enqueue(duplicate)).task_id == queued.task_id

    attempt_one = await queue.dequeue()
    assert attempt_one is not None
    await queue.fail(attempt_one.task_id, 'falha 1')
    retrying = await queue.get(queued.task_id)
    assert retrying is not None
    assert retrying.status == OperationalTaskStatus.PENDING
    assert retrying.next_attempt_at is not None

    attempt_two = await queue.dequeue()
    assert attempt_two is not None
    await queue.fail(attempt_two.task_id, 'falha 2')
    failed = await queue.get(queued.task_id)
    assert failed is not None
    assert failed.status == OperationalTaskStatus.DEAD_LETTER
    assert failed.last_error == 'falha 2'

    health = await queue.snapshot()
    assert health['provider'] == 'redis_streams'
    assert health['connected'] is True
    assert health['durable'] is True
    assert health['dlq_items'] == 1
    assert health['processing_items'] == 0


@pytest.mark.asyncio
async def test_unavailable_provider_fails_closed():
    queue = UnavailableOperationalQueue('redis_streams', 'Redis obrigatório')

    with pytest.raises(OperationalQueueUnavailableError, match='Redis obrigatório'):
        await queue.enqueue(
            OperationalTask(
                task_type=OperationalTaskType.GENERIC,
                payload={},
                correlation_id='corr-unavailable',
            )
        )

    health = await queue.snapshot()
    assert health['provider'] == 'redis_streams'
    assert health['connected'] is False
    assert health['error'] == 'Redis obrigatório'


def test_factory_rejects_memory_provider_in_production(monkeypatch):
    monkeypatch.setattr(settings, 'app_environment', 'production')
    monkeypatch.setattr(settings, 'operational_queue_provider', 'memory')

    queue = build_operational_queue()

    assert isinstance(queue, UnavailableOperationalQueue)
    assert queue.provider_name == 'redis_streams'


def test_factory_keeps_memory_provider_in_development(monkeypatch):
    monkeypatch.setattr(settings, 'app_environment', 'development')
    monkeypatch.setattr(settings, 'operational_queue_provider', 'memory')

    queue = build_operational_queue()

    assert isinstance(queue, OperationalQueue)
