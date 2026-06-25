from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Any


@dataclass
class RuntimeAnalyticsStore:
    max_snapshots: int = 100
    snapshots: deque[dict[str, Any]] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.max_snapshots < 1:
            raise ValueError('max_snapshots must be greater than zero')
        self.snapshots = deque(self.snapshots, maxlen=self.max_snapshots)

    def record(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        payload = dict(snapshot)
        payload['recorded_at'] = datetime.now(timezone.utc).isoformat()
        self.snapshots.append(payload)
        return payload

    def list_snapshots(self) -> list[dict[str, Any]]:
        return list(self.snapshots)


def _status_is_degraded(status: str) -> bool:
    return status in {'degraded', 'blocked', 'vermelho', 'bloqueado'}


def _trend(values: list[int | float]) -> str:
    if len(values) < 2:
        return 'insufficient_data'
    delta = values[-1] - values[0]
    if delta <= -5:
        return 'improving'
    if delta >= 5:
        return 'degrading'
    return 'stable'


def build_runtime_analytics(store: RuntimeAnalyticsStore, current_snapshot: dict[str, Any]) -> dict[str, Any]:
    recorded = store.record(current_snapshot)
    snapshots = store.list_snapshots()
    total = len(snapshots)
    degraded = [item for item in snapshots if _status_is_degraded(str(item.get('status', 'unknown')))]
    healthy = total - len(degraded)
    risk_scores = [int(item.get('risk_score', 0)) for item in snapshots]
    pending_items = [int(item.get('critical_counts', {}).get('pending_items', 0)) for item in snapshots]
    blocked_items = [int(item.get('critical_counts', {}).get('blocked_items', 0)) for item in snapshots]
    availability_score = round((healthy / total) * 100, 2) if total else 0
    failure_rate = round((len(degraded) / total) * 100, 2) if total else 0
    return {
        'schema_version': '1.0.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'correlation_id': recorded.get('correlation_id'),
        'window': {
            'mode': 'in_memory_rolling',
            'max_snapshots': store.max_snapshots,
            'total_snapshots': total,
        },
        'summary': {
            'current_status': recorded.get('status'),
            'current_risk_score': recorded.get('risk_score'),
            'average_risk_score': round(mean(risk_scores), 2) if risk_scores else 0,
            'max_risk_score': max(risk_scores) if risk_scores else 0,
            'availability_score': availability_score,
            'failure_rate': failure_rate,
            'degraded_snapshots': len(degraded),
            'healthy_snapshots': healthy,
        },
        'trends': {
            'risk_score': _trend(risk_scores),
            'pending_items': _trend(pending_items),
            'blocked_items': _trend(blocked_items),
        },
        'mttr': {
            'status': 'pending_persistent_storage',
            'value_seconds': None,
            'reason': 'requires durable incident lifecycle events',
        },
        'lead_time': {
            'status': 'pending_ci_deploy_integration',
            'value_seconds': None,
            'reason': 'requires deployment event timestamps',
        },
        'latest': snapshots[-10:],
        'guardrails': {
            'no_secrets': True,
            'no_pii': True,
            'read_only': True,
            'durable_storage_enabled': False,
        },
    }
