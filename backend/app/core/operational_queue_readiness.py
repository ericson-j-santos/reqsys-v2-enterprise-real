from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OperationalQueueReadinessPolicy:
    max_lag: int = 100
    max_pending: int = 50
    max_inactive_consumers: int = 0

    @classmethod
    def from_environment(cls) -> 'OperationalQueueReadinessPolicy':
        return cls(
            max_lag=_non_negative_int('OPERATIONAL_QUEUE_READY_MAX_LAG', 100),
            max_pending=_non_negative_int('OPERATIONAL_QUEUE_READY_MAX_PENDING', 50),
            max_inactive_consumers=_non_negative_int(
                'OPERATIONAL_QUEUE_READY_MAX_INACTIVE_CONSUMERS',
                0,
            ),
        )

    def evaluate(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        lag = int(snapshot.get('lag') or 0)
        pending = int(snapshot.get('pending') or 0)
        inactive = int(snapshot.get('consumers_inactive') or 0)
        reasons: list[str] = []

        if snapshot.get('status') == 'critical':
            reasons.extend(str(reason) for reason in snapshot.get('reasons') or [])
        if lag > self.max_lag:
            reasons.append('lag_threshold_exceeded')
        if pending > self.max_pending:
            reasons.append('pending_threshold_exceeded')
        if inactive > self.max_inactive_consumers:
            reasons.append('inactive_consumers_threshold_exceeded')

        unique_reasons = list(dict.fromkeys(reasons))
        return {
            'schema_version': '1.0.0',
            'component': 'operational_queue_readiness',
            'ready': not unique_reasons,
            'status': 'ready' if not unique_reasons else 'not_ready',
            'reasons': unique_reasons,
            'thresholds': {
                'max_lag': self.max_lag,
                'max_pending': self.max_pending,
                'max_inactive_consumers': self.max_inactive_consumers,
            },
            'observed': {
                'lag': lag,
                'pending': pending,
                'consumers_inactive': inactive,
                'consumer_status': snapshot.get('status'),
            },
            'source_timestamp': snapshot.get('timestamp'),
        }


def _non_negative_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f'{name} deve ser inteiro não negativo') from exc
    if value < 0:
        raise ValueError(f'{name} deve ser maior ou igual a zero')
    return value
