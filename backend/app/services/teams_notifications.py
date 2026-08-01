from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.integracao_log import IntegracaoLog
from app.models.teams_notification_queue import TeamsNotificationQueueItem
from app.schemas.teams_gateway import TeamsGatewayMessageRequest
from app.schemas.teams_notifications import TeamsNotificationEnqueueRequest
from app.services.teams_gateway import enviar_mensagem_gateway

logger = logging.getLogger('reqsys.teams_notifications')

_ALLOWED_STATUS = {'PENDENTE', 'PROCESSANDO', 'ENVIADO', 'FALHA', 'CANCELADO'}
_SENSITIVE_KEYS = ('token', 'secret', 'password', 'passwd', 'authorization', 'webhook', 'signature', 'api_key')


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if any(marker in normalized for marker in _SENSITIVE_KEYS):
                sanitized[str(key)] = '[REDACTED]'
            else:
                sanitized[str(key)] = _sanitize_metadata(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value[:100]]
    if isinstance(value, str):
        return value[:2000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:500]


def mascarar_destino(destino: str | None) -> tuple[str, str]:
    normalized = (destino or '').strip()
    if not normalized:
        return 'Automático/política', ''

    digest = hashlib.sha256(normalized.lower().encode('utf-8')).hexdigest()
    if '@' in normalized:
        local, domain = normalized.split('@', 1)
        local_masked = (local[:1] or '*') + '***'
        return f'{local_masked}@{domain}', digest
    if len(normalized) <= 8:
        return normalized[:2] + '***', digest
    return f'{normalized[:4]}…{normalized[-4:]}', digest


def _classificar_origem(
    *,
    metadata: dict[str, Any],
    titulo: str,
    mensagem: str,
    correlation_id: str,
) -> tuple[str, str, str]:
    joined = ' '.join(
        str(value)
        for value in (
            metadata.get('origem'),
            metadata.get('source'),
            metadata.get('event_type'),
            metadata.get('notification_type'),
            metadata.get('workflow'),
            titulo,
            mensagem,
            correlation_id,
        )
        if value
    ).lower()

    if 'hitl' in joined or 'approval' in joined or 'aprova' in joined:
        origem = 'hitl'
    elif 'commit' in joined or 'push' in joined:
        origem = 'commit'
    elif 'workflow' in joined or 'github action' in joined or ' ci ' in f' {joined} ':
        origem = 'ci'
    elif 'log' in joined or 'alert' in joined or 'falha operacional' in joined:
        origem = 'logs'
    elif 'manual' in joined:
        origem = 'manual'
    else:
        origem = 'gateway'

    tipo = str(
        metadata.get('event_type')
        or metadata.get('notification_type')
        or metadata.get('workflow')
        or origem
    )[:80]
    ambiente = str(
        metadata.get('environment')
        or metadata.get('ambiente')
        or metadata.get('branch')
        or 'unknown'
    )[:40]
    return origem, tipo, ambiente


def criar_item_fila(
    db: Session,
    payload: TeamsNotificationEnqueueRequest,
) -> TeamsNotificationQueueItem:
    masked, digest = mascarar_destino(payload.destino_id)
    correlation_id = payload.correlation_id or f'teams-notification-{uuid.uuid4()}'
    metadata = _sanitize_metadata(payload.metadata)
    metadata.update(
        {
            'origem': payload.origem,
            'event_type': payload.tipo_evento,
            'environment': payload.ambiente,
            'titulo': payload.titulo,
        }
    )

    item = TeamsNotificationQueueItem(
        origem=payload.origem,
        tipo_evento=payload.tipo_evento,
        ambiente=payload.ambiente,
        correlation_id=correlation_id,
        titulo=payload.titulo,
        texto=payload.texto,
        content_type=payload.content_type,
        autor=payload.autor,
        metadata_json=json.dumps(metadata, ensure_ascii=False, default=str),
        destino_tipo=payload.destino_tipo,
        destino_id=payload.destino_id,
        destino_mascarado=masked,
        destino_hash=digest,
        modo=payload.modo,
        permitir_fallback=payload.permitir_fallback,
        dry_run=payload.dry_run,
        status_evento='PENDENTE',
        tentativas=0,
        max_tentativas=payload.max_tentativas,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _gateway_request(item: TeamsNotificationQueueItem) -> TeamsGatewayMessageRequest:
    metadata = _parse_json(item.metadata_json)
    metadata['central_notification_event_id'] = item.id_evento
    metadata['origem'] = item.origem
    metadata['event_type'] = item.tipo_evento
    metadata['environment'] = item.ambiente
    metadata['titulo'] = item.titulo
    return TeamsGatewayMessageRequest(
        destino_tipo=item.destino_tipo,
        modo=item.modo,
        destino_id=item.destino_id,
        texto=item.texto,
        content_type=item.content_type,
        autor=item.autor,
        permitir_fallback=item.permitir_fallback,
        dry_run=item.dry_run,
        metadata=metadata,
    )


async def executar_item_fila(
    db: Session,
    item: TeamsNotificationQueueItem,
) -> TeamsNotificationQueueItem:
    if item.status_evento == 'PROCESSANDO':
        raise ValueError('Mensagem já está em processamento.')
    if item.tentativas >= item.max_tentativas:
        raise ValueError('Limite de tentativas atingido; exige nova mensagem governada.')

    item_id = item.id_evento
    item.status_evento = 'PROCESSANDO'
    item.tentativas += 1
    item.ultima_tentativa_em = _utcnow()
    item.motivo_falha = None
    db.commit()

    started = time.perf_counter()
    result: dict[str, Any]
    try:
        result = await enviar_mensagem_gateway(
            _gateway_request(item),
            db=db,
            correlation_id=f'{item.correlation_id}:attempt:{item.tentativas}',
        )
    except Exception as exc:
        logger.exception('teams_notification_send_unhandled event_id=%s', item_id)
        db.rollback()
        result = {
            'entregue': False,
            'canal_usado': None,
            'status_code': None,
            'message_id': None,
            'erro': type(exc).__name__,
            'motivo': str(exc)[:1000],
        }

    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    refreshed = db.get(TeamsNotificationQueueItem, item_id)
    if refreshed is None:
        raise RuntimeError(f'Evento de notificação não encontrado após envio: {item_id}')

    delivered = bool(result.get('entregue'))
    refreshed.status_evento = 'ENVIADO' if delivered else 'FALHA'
    refreshed.canal_usado = result.get('canal_usado')
    refreshed.status_http = result.get('status_code')
    refreshed.latencia_ms = latency_ms
    refreshed.provider_message_id = result.get('message_id')
    refreshed.motivo_falha = None if delivered else str(
        result.get('erro') or result.get('motivo') or 'Entrega não confirmada.'
    )[:2000]
    if delivered:
        refreshed.enviado_em = _utcnow()
    db.commit()
    db.refresh(refreshed)
    return refreshed


def serializar_item(item: TeamsNotificationQueueItem) -> dict[str, Any]:
    return {
        'id_evento': item.id_evento,
        'origem': item.origem,
        'tipo_evento': item.tipo_evento,
        'ambiente': item.ambiente,
        'upn_destino': item.destino_mascarado,
        'destino_hash': item.destino_hash,
        'titulo': item.titulo,
        'status_evento': item.status_evento,
        'tentativas': item.tentativas,
        'max_tentativas': item.max_tentativas,
        'canal_usado': item.canal_usado,
        'status_http': item.status_http,
        'latencia_ms': item.latencia_ms,
        'motivo_falha': item.motivo_falha,
        'correlation_id': item.correlation_id,
        'criado_em': item.criado_em.isoformat() if item.criado_em else None,
        'atualizado_em': item.atualizado_em.isoformat() if item.atualizado_em else None,
        'enviado_em': item.enviado_em.isoformat() if item.enviado_em else None,
    }


def _log_details(row: IntegracaoLog) -> tuple[dict[str, Any], dict[str, Any]]:
    details = _parse_json(row.detalhes)
    metadata = details.get('metadata')
    return details, metadata if isinstance(metadata, dict) else {}


def _log_is_central(details: dict[str, Any], metadata: dict[str, Any]) -> bool:
    return bool(metadata.get('central_notification_event_id') or details.get('central_notification_event_id'))


def _status_from_log(row: IntegracaoLog) -> str:
    return 'ENVIADO' if row.status == 'sucesso' else 'FALHA'


def _http_from_details(details: dict[str, Any]) -> int | None:
    provider = details.get('provider_response')
    if isinstance(provider, dict):
        value = provider.get('status_code')
        if isinstance(value, int):
            return value
    value = details.get('status_code')
    return value if isinstance(value, int) else None


def _historical_queue_row(row: IntegracaoLog) -> dict[str, Any]:
    details, metadata = _log_details(row)
    origem, tipo, ambiente = _classificar_origem(
        metadata=metadata,
        titulo=row.titulo or '',
        mensagem=row.mensagem or '',
        correlation_id=row.correlation_id or '',
    )
    return {
        'id_evento': f'historico-{row.id}',
        'origem': origem,
        'tipo_evento': tipo,
        'ambiente': ambiente,
        'upn_destino': 'Automático/política',
        'destino_hash': '',
        'titulo': row.titulo or 'Notificação Teams',
        'status_evento': _status_from_log(row),
        'tentativas': 1,
        'max_tentativas': 1,
        'canal_usado': details.get('canal_usado'),
        'status_http': _http_from_details(details),
        'latencia_ms': None,
        'motivo_falha': details.get('erro') if row.status != 'sucesso' else None,
        'correlation_id': row.correlation_id,
        'criado_em': row.criado_em.isoformat() if row.criado_em else None,
        'atualizado_em': row.criado_em.isoformat() if row.criado_em else None,
        'enviado_em': row.criado_em.isoformat() if row.status == 'sucesso' and row.criado_em else None,
    }


def listar_fila(
    db: Session,
    *,
    status: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    normalized_status = status.upper() if status else None
    if normalized_status and normalized_status not in _ALLOWED_STATUS:
        raise ValueError(f'Status inválido: {status}')

    stmt = select(TeamsNotificationQueueItem).order_by(
        desc(TeamsNotificationQueueItem.criado_em)
    )
    if normalized_status:
        stmt = stmt.where(TeamsNotificationQueueItem.status_evento == normalized_status)
    queue_rows = [serializar_item(item) for item in db.execute(stmt.limit(limit)).scalars().all()]

    historical: list[dict[str, Any]] = []
    if normalized_status in (None, 'ENVIADO', 'FALHA'):
        log_stmt = (
            select(IntegracaoLog)
            .where(IntegracaoLog.tipo == 'teams_gateway')
            .order_by(desc(IntegracaoLog.criado_em))
            .limit(limit * 2)
        )
        for row in db.execute(log_stmt).scalars().all():
            details, metadata = _log_details(row)
            if _log_is_central(details, metadata):
                continue
            mapped = _historical_queue_row(row)
            if normalized_status and mapped['status_evento'] != normalized_status:
                continue
            historical.append(mapped)
            if len(historical) >= limit:
                break

    combined = queue_rows + historical
    combined.sort(key=lambda item: item.get('criado_em') or '', reverse=True)
    return combined[:limit]


def listar_dlq(db: Session, *, limit: int) -> list[dict[str, Any]]:
    stmt = (
        select(TeamsNotificationQueueItem)
        .where(TeamsNotificationQueueItem.status_evento == 'FALHA')
        .order_by(desc(TeamsNotificationQueueItem.atualizado_em))
        .limit(limit)
    )
    return [
        {
            'id_dlq': item.id_evento,
            'id_evento': item.id_evento,
            'origem': item.origem,
            'tipo_evento': item.tipo_evento,
            'upn_destino': item.destino_mascarado,
            'motivo_falha': item.motivo_falha or 'Entrega não confirmada.',
            'tentativas': item.tentativas,
            'max_tentativas': item.max_tentativas,
            'correlation_id': item.correlation_id,
            'criado_em': item.criado_em.isoformat() if item.criado_em else None,
            'reprocessavel': item.tentativas < item.max_tentativas,
        }
        for item in db.execute(stmt).scalars().all()
    ]


def listar_logs(db: Session, *, limit: int) -> list[dict[str, Any]]:
    stmt = (
        select(IntegracaoLog)
        .where(IntegracaoLog.tipo == 'teams_gateway')
        .order_by(desc(IntegracaoLog.criado_em))
        .limit(limit)
    )
    logs: list[dict[str, Any]] = []
    for row in db.execute(stmt).scalars().all():
        details, metadata = _log_details(row)
        origem, tipo, ambiente = _classificar_origem(
            metadata=metadata,
            titulo=row.titulo or '',
            mensagem=row.mensagem or '',
            correlation_id=row.correlation_id or '',
        )
        central_id = metadata.get('central_notification_event_id')
        queue_item = db.get(TeamsNotificationQueueItem, central_id) if isinstance(central_id, int) else None
        status_http = _http_from_details(details)
        latency = queue_item.latencia_ms if queue_item else None
        detail_parts = [f'{origem}/{tipo}', f'ambiente={ambiente}']
        if row.correlation_id:
            detail_parts.append(f'correlation_id={row.correlation_id}')
        if latency is not None:
            detail_parts.append(f'latência={latency}ms')
        error = details.get('erro')
        if error:
            detail_parts.append(f'erro={str(error)[:300]}')
        logs.append(
            {
                'id_log': row.id,
                'id_evento': central_id or f'historico-{row.id}',
                'origem': origem,
                'tipo_evento': tipo,
                'ambiente': ambiente,
                'etapa': details.get('canal_usado') or 'teams_gateway',
                'status_resultado': _status_from_log(row),
                'status_http': status_http,
                'latencia_ms': latency,
                'correlation_id': row.correlation_id,
                'detalhe': ' · '.join(detail_parts),
                'registrado_em': row.criado_em.isoformat() if row.criado_em else None,
            }
        )
    return logs


def obter_dashboard(db: Session, *, window_days: int = 30) -> dict[str, Any]:
    queue_items = list(db.execute(select(TeamsNotificationQueueItem)).scalars().all())
    counts = Counter(item.status_evento for item in queue_items)
    origins = Counter(item.origem for item in queue_items)

    cutoff = _utcnow() - timedelta(days=window_days)
    historical_stmt = (
        select(IntegracaoLog)
        .where(IntegracaoLog.tipo == 'teams_gateway')
        .where(IntegracaoLog.criado_em >= cutoff)
        .order_by(desc(IntegracaoLog.criado_em))
    )
    historical_total = 0
    historical_success = 0
    last_update: datetime | None = None
    for row in db.execute(historical_stmt).scalars().all():
        details, metadata = _log_details(row)
        if _log_is_central(details, metadata):
            continue
        historical_total += 1
        historical_success += 1 if row.status == 'sucesso' else 0
        origem, _, _ = _classificar_origem(
            metadata=metadata,
            titulo=row.titulo or '',
            mensagem=row.mensagem or '',
            correlation_id=row.correlation_id or '',
        )
        origins[origem] += 1
        if row.criado_em and (last_update is None or row.criado_em > last_update):
            last_update = row.criado_em

    sent = counts['ENVIADO'] + historical_success
    failed = counts['FALHA'] + (historical_total - historical_success)
    pending = counts['PENDENTE']
    processing = counts['PROCESSANDO']
    completed = sent + failed
    latencies = [item.latencia_ms for item in queue_items if item.latencia_ms is not None]

    for item in queue_items:
        candidate = item.atualizado_em or item.criado_em
        if candidate and (last_update is None or candidate > last_update):
            last_update = candidate

    return {
        'schema_version': '1.0.0',
        'window_days': window_days,
        'pendentes': pending,
        'processando': processing,
        'enviados': sent,
        'falhas': failed,
        'cancelados': counts['CANCELADO'],
        'total': pending + processing + sent + failed + counts['CANCELADO'],
        'taxa_sucesso_percentual': round(sent / completed * 100, 2) if completed else 0.0,
        'latencia_media_ms': round(sum(latencies) / len(latencies), 2) if latencies else None,
        'por_origem': dict(sorted(origins.items())),
        'ultima_atualizacao': last_update.isoformat() if last_update else None,
        'cobertura': {
            'commit': True,
            'ci': True,
            'logs': True,
            'hitl': True,
            'manual': True,
            'correlation_id': True,
            'destinatario_sanitizado': True,
            'dlq_reprocessamento': True,
        },
    }
