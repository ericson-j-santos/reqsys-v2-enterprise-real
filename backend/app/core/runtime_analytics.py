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
_INCIDENT_OPEN_STATUSES = {'degraded', 'blocked', 'vermelho', 'bloqueado'}
_INCIDENT_RESOLVED_STATUSES = {'healthy', 'ok', 'green', 'verde', 'attention'}
_DEPLOY_STARTED_EVENTS = {'deploy_started', 'deployment_started'}
_DEPLOY_FINISHED_EVENTS = {'deploy_finished', 'deployment_finished', 'deploy_succeeded', 'deployment_succeeded'}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


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


def _incident_key(snapshot: dict[str, Any]) -> str:
    evidence = snapshot.get('evidence') or {}
    explicit_key = evidence.get('incident_key') or evidence.get('runtime_component')
    if explicit_key:
        return str(explicit_key)[:128]
    return 'runtime-health'


def _deploy_key(payload: dict[str, Any]) -> str:
    explicit_key = payload.get('deploy_key') or payload.get('deployment_key') or payload.get('version')
    if explicit_key:
        return str(explicit_key)[:128]
    return 'runtime-deploy'


def _deployment_environment(payload: dict[str, Any]) -> str:
    return str(payload.get('environment') or payload.get('target_environment') or 'unknown')[:64]


class RuntimeAnalyticsStoreProtocol(Protocol):
    max_snapshots: int

    def record(self, snapshot: dict[str, Any]) -> dict[str, Any]: ...

    def list_snapshots(self) -> list[dict[str, Any]]: ...

    def storage_mode(self) -> str: ...

    def durable_storage_enabled(self) -> bool: ...

    def record_incident_event(self, snapshot: dict[str, Any]) -> dict[str, Any] | None: ...

    def list_incident_events(self) -> list[dict[str, Any]]: ...

    def record_deploy_event(self, deploy_event: dict[str, Any]) -> dict[str, Any] | None: ...

    def list_deploy_events(self) -> list[dict[str, Any]]: ...


@dataclass
class RuntimeAnalyticsStore:
    max_snapshots: int = 100
    snapshots: deque[dict[str, Any]] = field(default_factory=deque)
    incident_events: deque[dict[str, Any]] = field(default_factory=deque)
    deploy_events: deque[dict[str, Any]] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.max_snapshots < 1:
            raise ValueError('max_snapshots must be greater than zero')
        self.snapshots = deque(self.snapshots, maxlen=self.max_snapshots)
        self.incident_events = deque(self.incident_events, maxlen=self.max_snapshots)
        self.deploy_events = deque(self.deploy_events, maxlen=self.max_snapshots)

    def record(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        payload = _sanitize_snapshot(snapshot)
        payload['recorded_at'] = _utc_now().isoformat()
        self.snapshots.append(payload)
        return payload

    def list_snapshots(self) -> list[dict[str, Any]]:
        return list(self.snapshots)

    def record_incident_event(self, snapshot: dict[str, Any]) -> dict[str, Any] | None:
        event = build_incident_event(snapshot, self.list_incident_events())
        if event is None:
            return None
        self.incident_events.append(event)
        return event

    def list_incident_events(self) -> list[dict[str, Any]]:
        return list(self.incident_events)

    def record_deploy_event(self, deploy_event: dict[str, Any]) -> dict[str, Any] | None:
        event = sanitize_deploy_event(deploy_event)
        if event is None:
            return None
        self.deploy_events.append(event)
        return event

    def list_deploy_events(self) -> list[dict[str, Any]]:
        return list(self.deploy_events)

    def storage_mode(self) -> str:
        return 'in_memory_rolling'

    def durable_storage_enabled(self) -> bool:
        return False


@dataclass
class DurableRuntimeAnalyticsStore:
    database_url: str
    max_snapshots: int = 100
    table_name: str = 'runtime_operational_snapshots'
    incident_table_name: str = 'runtime_incident_events'
    deploy_table_name: str = 'runtime_deploy_events'
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
        self.incident_table = Table(
            self.incident_table_name,
            self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('event_at', DateTime(timezone=True), nullable=False, index=True),
            Column('incident_key', String(128), nullable=False, index=True),
            Column('event_type', String(32), nullable=False, index=True),
            Column('status', String(32), nullable=False, index=True),
            Column('correlation_id', String(128), nullable=True, index=True),
            Column('payload_json', Text, nullable=False),
        )
        self.deploy_table = Table(
            self.deploy_table_name,
            self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('event_at', DateTime(timezone=True), nullable=False, index=True),
            Column('deploy_key', String(128), nullable=False, index=True),
            Column('event_type', String(32), nullable=False, index=True),
            Column('environment', String(64), nullable=False, index=True),
            Column('correlation_id', String(128), nullable=True, index=True),
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

    def record_incident_event(self, snapshot: dict[str, Any]) -> dict[str, Any] | None:
        if self.engine is None:
            raise RuntimeError('runtime analytics engine not initialized')

        event = build_incident_event(snapshot, self.list_incident_events())
        if event is None:
            return None
        event_at = _parse_dt(event.get('event_at')) or _utc_now()
        payload_json = json.dumps(event, ensure_ascii=False, sort_keys=True)

        with self.engine.begin() as conn:
            conn.execute(
                insert(self.incident_table).values(
                    event_at=event_at,
                    incident_key=event['incident_key'],
                    event_type=event['event_type'],
                    status=event['status'],
                    correlation_id=event.get('correlation_id'),
                    payload_json=payload_json,
                )
            )
        return event

    def list_incident_events(self) -> list[dict[str, Any]]:
        if self.engine is None:
            raise RuntimeError('runtime analytics engine not initialized')

        stmt = select(self.incident_table.c.payload_json).order_by(self.incident_table.c.event_at.desc(), self.incident_table.c.id.desc()).limit(self.max_snapshots)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).scalars().all()
        return [json.loads(item) for item in reversed(rows)]

    def record_deploy_event(self, deploy_event: dict[str, Any]) -> dict[str, Any] | None:
        if self.engine is None:
            raise RuntimeError('runtime analytics engine not initialized')

        event = sanitize_deploy_event(deploy_event)
        if event is None:
            return None
        event_at = _parse_dt(event.get('event_at')) or _utc_now()
        payload_json = json.dumps(event, ensure_ascii=False, sort_keys=True)

        with self.engine.begin() as conn:
            conn.execute(
                insert(self.deploy_table).values(
                    event_at=event_at,
                    deploy_key=event['deploy_key'],
                    event_type=event['event_type'],
                    environment=event['environment'],
                    correlation_id=event.get('correlation_id'),
                    payload_json=payload_json,
                )
            )
        return event

    def list_deploy_events(self) -> list[dict[str, Any]]:
        if self.engine is None:
            raise RuntimeError('runtime analytics engine not initialized')

        stmt = select(self.deploy_table.c.payload_json).order_by(self.deploy_table.c.event_at.desc(), self.deploy_table.c.id.desc()).limit(self.max_snapshots)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).scalars().all()
        return [json.loads(item) for item in reversed(rows)]

    def storage_mode(self) -> str:
        return 'durable_sql'

    def durable_storage_enabled(self) -> bool:
        return True


def _status_is_degraded(status: str) -> bool:
    return status in _INCIDENT_OPEN_STATUSES


def _trend(values: list[int | float]) -> str:
    if len(values) < 2:
        return 'insufficient_data'
    delta = values[-1] - values[0]
    if delta <= -5:
        return 'improving'
    if delta >= 5:
        return 'degrading'
    return 'stable'


def _last_event_for_key(events: list[dict[str, Any]], incident_key: str) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get('incident_key') == incident_key:
            return event
    return None


def build_incident_event(snapshot: dict[str, Any], previous_events: list[dict[str, Any]]) -> dict[str, Any] | None:
    payload = _sanitize_snapshot(snapshot)
    status = str(payload.get('status', 'unknown'))
    incident_key = _incident_key(payload)
    last_event = _last_event_for_key(previous_events, incident_key)
    last_event_type = str(last_event.get('event_type')) if last_event else None

    event_type: str | None = None
    if status in _INCIDENT_OPEN_STATUSES and last_event_type not in {'incident_opened', 'incident_acknowledged'}:
        event_type = 'incident_opened'
    elif status in _INCIDENT_OPEN_STATUSES and last_event_type == 'incident_opened':
        event_type = 'incident_acknowledged'
    elif status in _INCIDENT_RESOLVED_STATUSES and last_event_type in {'incident_opened', 'incident_acknowledged'}:
        event_type = 'incident_resolved'

    if event_type is None:
        return None

    event_at = _utc_now().isoformat()
    return {
        'event_type': event_type,
        'event_at': event_at,
        'incident_key': incident_key,
        'status': status,
        'risk_score': int(payload.get('risk_score', 0) or 0),
        'correlation_id': payload.get('correlation_id'),
        'critical_counts': payload.get('critical_counts') or {},
    }


def sanitize_deploy_event(deploy_event: dict[str, Any]) -> dict[str, Any] | None:
    event_type = str(deploy_event.get('event_type') or '')
    if event_type not in _DEPLOY_STARTED_EVENTS | _DEPLOY_FINISHED_EVENTS:
        return None

    event_at = _parse_dt(deploy_event.get('event_at')) or _utc_now()
    return {
        'event_type': 'deploy_started' if event_type in _DEPLOY_STARTED_EVENTS else 'deploy_finished',
        'event_at': event_at.isoformat(),
        'deploy_key': _deploy_key(deploy_event),
        'environment': _deployment_environment(deploy_event),
        'correlation_id': deploy_event.get('correlation_id'),
        'commit_sha': str(deploy_event.get('commit_sha') or '')[:64] or None,
        'source': str(deploy_event.get('source') or 'runtime')[:64],
    }


def build_mttr(events: list[dict[str, Any]]) -> dict[str, Any]:
    opened_by_key: dict[str, datetime] = {}
    durations: list[int] = []
    resolved_count = 0

    for event in events:
        incident_key = str(event.get('incident_key', 'runtime-health'))
        event_type = str(event.get('event_type'))
        event_at = _parse_dt(event.get('event_at'))
        if event_at is None:
            continue
        if event_type == 'incident_opened':
            opened_by_key[incident_key] = event_at
        elif event_type == 'incident_resolved' and incident_key in opened_by_key:
            resolved_count += 1
            durations.append(max(0, int((event_at - opened_by_key[incident_key]).total_seconds())))
            opened_by_key.pop(incident_key, None)

    if not durations:
        return {
            'status': 'insufficient_resolved_incidents',
            'value_seconds': None,
            'resolved_incidents': resolved_count,
            'open_incidents': len(opened_by_key),
            'reason': 'requires at least one opened and resolved incident lifecycle',
        }

    return {
        'status': 'calculated',
        'value_seconds': round(mean(durations), 2),
        'resolved_incidents': resolved_count,
        'open_incidents': len(opened_by_key),
        'min_seconds': min(durations),
        'max_seconds': max(durations),
    }


def build_lead_time(events: list[dict[str, Any]]) -> dict[str, Any]:
    started_by_key: dict[str, datetime] = {}
    durations: list[int] = []
    finished_count = 0

    for event in events:
        deploy_key = str(event.get('deploy_key', 'runtime-deploy'))
        event_type = str(event.get('event_type'))
        event_at = _parse_dt(event.get('event_at'))
        if event_at is None:
            continue
        if event_type == 'deploy_started':
            started_by_key[deploy_key] = event_at
        elif event_type == 'deploy_finished' and deploy_key in started_by_key:
            finished_count += 1
            durations.append(max(0, int((event_at - started_by_key[deploy_key]).total_seconds())))
            started_by_key.pop(deploy_key, None)

    if not durations:
        return {
            'status': 'insufficient_deploy_events',
            'value_seconds': None,
            'finished_deploys': finished_count,
            'open_deploys': len(started_by_key),
            'reason': 'requires at least one deploy_started and deploy_finished event pair',
        }

    return {
        'status': 'calculated',
        'value_seconds': round(mean(durations), 2),
        'finished_deploys': finished_count,
        'open_deploys': len(started_by_key),
        'min_seconds': min(durations),
        'max_seconds': max(durations),
    }


def extract_deploy_event(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    evidence = snapshot.get('evidence') or {}
    deploy_payload = evidence.get('deploy_event') or evidence.get('deployment_event')
    if isinstance(deploy_payload, dict):
        return deploy_payload
    return None


def build_runtime_analytics(store: RuntimeAnalyticsStoreProtocol, current_snapshot: dict[str, Any]) -> dict[str, Any]:
    recorded = store.record(current_snapshot)
    incident_event = store.record_incident_event(recorded)
    deploy_event = None
    extracted_deploy_event = extract_deploy_event(recorded)
    if extracted_deploy_event is not None:
        deploy_event = store.record_deploy_event(extracted_deploy_event)

    snapshots = store.list_snapshots()
    incident_events = store.list_incident_events()
    deploy_events = store.list_deploy_events()
    total = len(snapshots)
    degraded = [item for item in snapshots if _status_is_degraded(str(item.get('status', 'unknown')))]
    healthy = total - len(degraded)
    risk_scores = [int(item.get('risk_score', 0)) for item in snapshots]
    pending_items = [int(item.get('critical_counts', {}).get('pending_items', 0)) for item in snapshots]
    blocked_items = [int(item.get('critical_counts', {}).get('blocked_items', 0)) for item in snapshots]
    availability_score = round((healthy / total) * 100, 2) if total else 0
    failure_rate = round((len(degraded) / total) * 100, 2) if total else 0
    durable_enabled = store.durable_storage_enabled()
    mttr = build_mttr(incident_events)
    lead_time = build_lead_time(deploy_events)
    return {
        'schema_version': '1.3.0',
        'generated_at': _utc_now().isoformat(),
        'correlation_id': recorded.get('correlation_id'),
        'window': {
            'mode': store.storage_mode(),
            'max_snapshots': store.max_snapshots,
            'total_snapshots': total,
            'total_incident_events': len(incident_events),
            'total_deploy_events': len(deploy_events),
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
        'incident_lifecycle': {
            'last_event': incident_event,
            'events': incident_events[-10:],
            'supported_events': ['incident_opened', 'incident_acknowledged', 'incident_resolved'],
        },
        'deploy_lifecycle': {
            'last_event': deploy_event,
            'events': deploy_events[-10:],
            'supported_events': ['deploy_started', 'deploy_finished'],
        },
        'mttr': mttr,
        'lead_time': lead_time,
        'latest': snapshots[-10:],
        'guardrails': {
            'no_secrets': True,
            'no_pii': True,
            'read_only': True,
            'durable_storage_enabled': durable_enabled,
            'storage_mode': store.storage_mode(),
            'incident_lifecycle_enabled': True,
            'deploy_lifecycle_enabled': True,
        },
    }
