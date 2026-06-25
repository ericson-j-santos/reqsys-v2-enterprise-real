import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Protocol

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
    select,
)


_ALLOWED_SNAPSHOT_FIELDS = {
    'correlation_id',
    'generated_at',
    'status',
    'risk_score',
    'critical_counts',
    'evidence',
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _sanitize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Persist only the operational allowlist required for analytics.

    Runtime analytics must not become a data lake for arbitrary payloads. The
    endpoint only needs operational counters/status/risk metadata, so the store
    records an allowlisted subset to preserve the no-PII/no-secret guardrail.
    """

    payload = {key: snapshot[key] for key in _ALLOWED_SNAPSHOT_FIELDS if key in snapshot}
    payload['critical_counts'] = dict(payload.get('critical_counts') or {})
    payload['evidence'] = dict(payload.get('evidence') or {})
    return payload


class RuntimeAnalyticsStoreProtocol(Protocol):
    max_snapshots: int

    def record(self, snapshot: dict[str, Any]) -> dict[str, Any]: ...

    def list_snapshots(self) -> list[dict[str, Any]]: ...

    def storage_mode(self) -> str: ...

    def durable_storage_enabled(self) -> bool: ...


@dataclass
class RuntimeAnalyticsStore:
    max_snapshots: int = 100
    snapshots: deque[dict[str, Any]] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.max_snapshots < 1:
            raise ValueError('max_snapshots must be greater than zero')
        self.snapshots = deque(self.snapshots, maxlen=self.max_snapshots)

    def record(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        payload = _sanitize_snapshot(snapshot)
        payload['recorded_at'] = _utc_now().isoformat()
        self.snapshots.append(payload)
        return payload

    def list_snapshots(self) -> list[dict[str, Any]]:
        return list(self.snapshots)

    def storage_mode(self) -> str:
        return 'in_memory_rolling'

    def durable_storage_enabled(self) -> bool:
        return False


@dataclass
class DurableRuntimeAnalyticsStore:
    database_url: str
    max_snapshots: int = 100
    table_name: str = 'runtime_operational_snapshots'
    engine: Any | None = None
    metadata: MetaData = field(default_factory=MetaData)

    def __post_init__(self) -> None:
        if self.max_snapshots < 1:
            raise ValueError('max_snapshots must be greater than zero')
        connect_args = {'check_same_thread': False} if self.database_url.startswith('sqlite') else {}
        self.engine = self.engine or create_engine(self.database_url, connect_args=connect_args)
        self.table = Table(
            self.table_name,
            self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('recorded_at', DateTime(timezone=True), nullable=False, index=True),
            Column('correlation_id', String(128), nullable=True, index=True),
            Column('status', String(32), nullable=False, index=True),
            Column('risk_score', Integer, nullable=False),
            Column('payload_json', Text, nullable=False),
        )
        self.metadata.create_all(self.engine)

    def record(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if self.engine is None:
            raise RuntimeError('runtime analytics engine not initialized')

        payload = _sanitize_snapshot(snapshot)
        recorded_at = _utc_now()
        payload['recorded_at'] = recorded_at.isoformat()
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        status = str(payload.get('status', 'unknown'))
        risk_score = int(payload.get('risk_score', 0) or 0)
        correlation_id = payload.get('correlation_id')

        with self.engine.begin() as conn:
            conn.execute(
                insert(self.table).values(
                    recorded_at=recorded_at,
                    correlation_id=str(correlation_id) if correlation_id else None,
                    status=status,
                    risk_score=risk_score,
                    payload_json=payload_json,
                )
            )
        return payload

    def list_snapshots(self) -> list[dict[str, Any]]:
        if self.engine is None:
            raise RuntimeError('runtime analytics engine not initialized')

        stmt = select(self.table.c.payload_json).order_by(self.table.c.recorded_at.desc(), self.table.c.id.desc()).limit(self.max_snapshots)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).scalars().all()
        return [json.loads(item) for item in reversed(rows)]

    def storage_mode(self) -> str:
        return 'durable_sql'

    def durable_storage_enabled(self) -> bool:
        return True


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


def build_runtime_analytics(store: RuntimeAnalyticsStoreProtocol, current_snapshot: dict[str, Any]) -> dict[str, Any]:
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
    durable_enabled = store.durable_storage_enabled()
    return {
        'schema_version': '1.1.0',
        'generated_at': _utc_now().isoformat(),
        'correlation_id': recorded.get('correlation_id'),
        'window': {
            'mode': store.storage_mode(),
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
            'status': 'pending_incident_lifecycle_events',
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
            'durable_storage_enabled': durable_enabled,
            'storage_mode': store.storage_mode(),
        },
    }
