from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models.auditoria import AuditoriaEvento

_COMPLETED = 'AI_CONVERSATION_TEAMS_MESSAGE_COMPLETED'
_FAILED = 'AI_CONVERSATION_TEAMS_MESSAGE_FAILED'
_ACTIONS = (_COMPLETED, _FAILED)


def _percentile_95(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(0.95 * len(ordered) + 0.5) - 1))
    return ordered[index]


def _payload(event: AuditoriaEvento) -> dict[str, Any]:
    try:
        value = json.loads(event.payload_minimo or '{}')
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def construir_snapshot_teams_inbound(
    events: Iterable[AuditoriaEvento],
    *,
    window_minutes: int,
) -> dict[str, Any]:
    completed = 0
    failed = 0
    duplicates = 0
    responses_sent = 0
    latencies: list[int] = []
    last_event_at: str | None = None

    for event in events:
        payload = _payload(event)
        if payload.get('channel') != 'teams_bot':
            continue
        if event.acao == _COMPLETED:
            completed += 1
            duplicates += int(payload.get('duplicate') is True)
            responses_sent += int(payload.get('response_sent') is True)
        elif event.acao == _FAILED:
            failed += 1
        else:
            continue
        latency = payload.get('latency_ms')
        if isinstance(latency, int) and latency >= 0:
            latencies.append(latency)
        if last_event_at is None and event.criado_em is not None:
            last_event_at = event.criado_em.isoformat()

    total = completed + failed
    failure_rate = round((failed / total) * 100, 2) if total else 0.0
    average_latency = round(mean(latencies), 2) if latencies else None
    alerts: list[str] = []
    status = 'unknown'
    if total:
        status = 'healthy'
        if failure_rate >= 20:
            status = 'degraded'
            alerts.append('teams_inbound_failure_rate_high')
        elif failed:
            status = 'attention'
            alerts.append('teams_inbound_failures_detected')
        if average_latency is not None and average_latency >= 10000:
            status = 'degraded'
            alerts.append('teams_inbound_latency_critical')
        elif average_latency is not None and average_latency >= 5000:
            if status == 'healthy':
                status = 'attention'
            alerts.append('teams_inbound_latency_high')

    return {
        'schema_version': '1.0.0',
        'channel': 'teams_bot',
        'window_minutes': window_minutes,
        'status': status,
        'alert_required': status in {'attention', 'degraded'},
        'alerts': alerts,
        'metrics': {
            'total': total,
            'completed': completed,
            'failed': failed,
            'failure_rate_percent': failure_rate,
            'duplicates': duplicates,
            'responses_sent': responses_sent,
            'latency_average_ms': average_latency,
            'latency_p95_ms': _percentile_95(latencies),
            'last_event_at': last_event_at,
        },
        'privacy': {
            'message_content_included': False,
            'user_identity_included': False,
            'provider_response_included': False,
        },
    }


def obter_snapshot_teams_inbound(
    db: Session,
    *,
    window_minutes: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    reference = now or datetime.now(timezone.utc)
    cutoff = reference - timedelta(minutes=window_minutes)
    events = (
        db.query(AuditoriaEvento)
        .filter(
            AuditoriaEvento.entidade == 'ai_conversation',
            AuditoriaEvento.acao.in_(_ACTIONS),
            AuditoriaEvento.criado_em >= cutoff,
        )
        .order_by(AuditoriaEvento.criado_em.desc())
        .limit(500)
        .all()
    )
    return construir_snapshot_teams_inbound(events, window_minutes=window_minutes)
