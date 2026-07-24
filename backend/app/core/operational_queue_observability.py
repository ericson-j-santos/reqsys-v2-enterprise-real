from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.operational_queue import (
    OperationalQueueUnavailableError,
    RedisStreamsOperationalQueue,
    operational_queue,
)


@dataclass(frozen=True, slots=True)
class ConsumerHealth:
    name: str
    pending: int
    idle_ms: int
    inactive: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'pending': self.pending,
            'idle_ms': self.idle_ms,
            'inactive': self.inactive,
        }


class OperationalQueueObserver:
    """Produz evidência operacional do consumer group Redis Streams."""

    def __init__(
        self,
        queue: Any = operational_queue,
        *,
        inactive_consumer_ms: int = 300_000,
    ) -> None:
        if inactive_consumer_ms <= 0:
            raise ValueError('inactive_consumer_ms deve ser maior que zero')
        self.queue = queue
        self.inactive_consumer_ms = inactive_consumer_ms

    def _redis_queue(self) -> RedisStreamsOperationalQueue:
        if not isinstance(self.queue, RedisStreamsOperationalQueue):
            raise OperationalQueueUnavailableError(
                'Observabilidade detalhada exige OPERATIONAL_QUEUE_PROVIDER=redis_streams'
            )
        return self.queue

    async def snapshot(self) -> dict[str, Any]:
        queue = self._redis_queue()
        await queue._ensure_group()

        try:
            groups = await queue._redis.xinfo_groups(queue._stream_key)
            consumers = await queue._redis.xinfo_consumers(
                queue._stream_key,
                queue._consumer_group,
            )
            pending_summary = await queue._redis.xpending(
                queue._stream_key,
                queue._consumer_group,
            )
        except Exception as exc:
            raise OperationalQueueUnavailableError(
                f'Falha ao coletar observabilidade do Redis Streams: {exc}'
            ) from exc

        group = next(
            (item for item in groups if item.get('name') == queue._consumer_group),
            {},
        )
        consumer_health = [
            ConsumerHealth(
                name=str(item.get('name', 'unknown')),
                pending=int(item.get('pending') or 0),
                idle_ms=int(item.get('idle') or 0),
                inactive=int(item.get('idle') or 0) >= self.inactive_consumer_ms,
            )
            for item in consumers
        ]
        pending_count = self._pending_count(pending_summary)
        inactive_count = sum(1 for item in consumer_health if item.inactive)

        status = 'healthy'
        reasons: list[str] = []
        if inactive_count:
            status = 'degraded'
            reasons.append('inactive_consumers')
        if pending_count and not consumers:
            status = 'critical'
            reasons.append('pending_without_consumers')

        return {
            'schema_version': '1.0.0',
            'component': 'operational_queue_consumers',
            'status': status,
            'reasons': reasons,
            'provider': queue.provider_name,
            'stream': queue._stream_key,
            'consumer_group': queue._consumer_group,
            'consumer_name': queue._consumer_name,
            'lag': int(group.get('lag') or 0),
            'pending': pending_count,
            'consumers_total': len(consumer_health),
            'consumers_inactive': inactive_count,
            'inactive_threshold_ms': self.inactive_consumer_ms,
            'consumers': [item.to_dict() for item in consumer_health],
            'timestamp': datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _pending_count(summary: Any) -> int:
        if isinstance(summary, dict):
            return int(summary.get('pending') or 0)
        if isinstance(summary, (list, tuple)) and summary:
            return int(summary[0] or 0)
        return 0


async def build_observability_report() -> dict[str, Any]:
    return await OperationalQueueObserver().snapshot()


async def _main() -> None:
    report = await build_observability_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    import asyncio

    asyncio.run(_main())
