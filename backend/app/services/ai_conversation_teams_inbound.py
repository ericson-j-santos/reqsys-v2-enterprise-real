from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.correlation import resolver_correlation_id
from app.db import SessionLocal
from app.models.ai_conversation import AIConversation
from app.schemas.ai_conversation import AIConversationCreateRequest
from app.services.ai_conversation import (
    AIConversationError,
    criar_conversa,
    executar_turno,
    obter_conversa,
    status_provedores,
)
from app.services.auditoria import registrar_evento
from app.services.teams_gateway import (
    _enviar_atividade_bot_framework,
    diagnosticar_propriedade_conversa_referencia,
    obter_conversa_referencia_bot,
)

logger = logging.getLogger('reqsys.ai_conversation_teams_inbound')

_PROVIDER_PRIORITY = ('ollama_gateway', 'gemini', 'groq', 'openai', 'claude', 'ollama')


def _teams_chat_area_id(teams_conversation_id: str) -> str:
    digest = hashlib.sha256(teams_conversation_id.encode('utf-8')).hexdigest()[:32]
    return f'teams-inbound:{digest}'


def _modelo_provider(provider: str) -> str:
    models = {
        'ollama_gateway': settings.codex_ollama_gateway_model or settings.codex_ollama_model,
        'ollama': settings.codex_ollama_model,
        'gemini': settings.gemini_model,
        'groq': settings.groq_model,
        'openai': settings.codex_openai_model,
        'claude': settings.codex_claude_model,
    }
    return models[provider]


def selecionar_provedor_teams() -> tuple[str, str]:
    configurados = status_provedores()
    preferido = (settings.ai_default_provider or '').strip().lower()
    candidatos = (preferido, *_PROVIDER_PRIORITY)
    for provider in candidatos:
        if provider and configurados.get(provider, {}).get('configurado') is True:
            return provider, _modelo_provider(provider)
    raise RuntimeError('teams_inbound_provider_unavailable')


def _conversa_recente(
    db: Session,
    *,
    usuario_aad_object_id: str,
    tenant_id: str,
    teams_chat_area_id: str,
) -> AIConversation | None:
    stmt = (
        select(AIConversation)
        .where(
            AIConversation.teams_destino_id == usuario_aad_object_id,
            AIConversation.teams_modo == 'bot',
            AIConversation.area_id == teams_chat_area_id,
            AIConversation.status != 'encerrada',
        )
        .order_by(desc(AIConversation.ultima_mensagem_em), desc(AIConversation.criado_em))
        .limit(1)
    )
    if tenant_id:
        stmt = stmt.where(AIConversation.tenant_id == tenant_id)
    return db.execute(stmt).scalar_one_or_none()


def _criar_conversa_teams(
    db: Session,
    *,
    mensagem: str,
    usuario_aad_object_id: str,
    tenant_id: str,
    teams_chat_area_id: str,
    correlation_id: str,
) -> AIConversation:
    provider, model = selecionar_provedor_teams()
    payload = AIConversationCreateRequest(
        provider=provider,
        model=model,
        mensagem=mensagem,
        data_classification='internal',
        tenant_id=tenant_id or 'teams-dev',
        area_id=teams_chat_area_id,
        requester_id=usuario_aad_object_id,
        cost_center='teams-bot',
        titulo='Conversa pelo Microsoft Teams',
        origem='teams',
        teams_destino_tipo='chat_1a1',
        teams_destino_id=usuario_aad_object_id,
        teams_modo='bot',
        teams_permitir_fallback=False,
        enviar_teams=False,
    )
    return criar_conversa(db, payload, correlation_id=correlation_id)


async def _responder_no_chat(
    db: Session,
    *,
    usuario_aad_object_id: str,
    resposta: str,
    activity_id: str,
) -> None:
    referencia = obter_conversa_referencia_bot(db, usuario_aad_object_id)
    if referencia is None:
        raise RuntimeError('conversation_reference_missing')
    ownership_failure = diagnosticar_propriedade_conversa_referencia(referencia)
    if ownership_failure:
        raise RuntimeError(ownership_failure)
    url = (
        f"{referencia.service_url.rstrip('/')}"
        f'/v3/conversations/{referencia.conversation_id}/activities'
    )
    payload: dict[str, Any] = {
        'type': 'message',
        'from': {'id': settings.teams_bot_app_id},
        'conversation': {'id': referencia.conversation_id},
        'text': resposta[:20000],
        'textFormat': 'plain',
    }
    if activity_id:
        payload['replyToId'] = activity_id
    await _enviar_atividade_bot_framework(url, payload)


async def processar_activity_teams_bot(db: Session, activity: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    if str(activity.get('type') or '').strip().lower() != 'message':
        return {'processado': False, 'motivo': 'activity_type_ignored'}

    remetente = activity.get('from') or {}
    usuario_aad_object_id = str(remetente.get('aadObjectId') or '').strip()
    if not usuario_aad_object_id:
        return {'processado': False, 'motivo': 'sender_aad_object_id_missing'}

    value = activity.get('value') or {}
    action = value.get('reqsys_action') if isinstance(value, dict) else None
    mensagem = str(
        (value.get('mensagem') if isinstance(value, dict) else '')
        or activity.get('text')
        or ''
    ).strip()
    if not mensagem:
        return {'processado': False, 'motivo': 'message_empty'}

    activity_id = str(activity.get('id') or '').strip()
    teams_conversation_id = str((activity.get('conversation') or {}).get('id') or '').strip()
    if not teams_conversation_id:
        return {'processado': False, 'motivo': 'teams_conversation_id_missing'}
    teams_chat_area_id = _teams_chat_area_id(teams_conversation_id)
    tenant_id = str(((activity.get('channelData') or {}).get('tenant') or {}).get('id') or '').strip()
    supplied_correlation_id = value.get('correlation_id') if isinstance(value, dict) else None
    correlation_id = resolver_correlation_id(str(supplied_correlation_id or '').strip() or None, None)

    if action == 'ai_conversation_reply':
        conversation_id = str(value.get('conversation_id') or '').strip()
        if not conversation_id:
            raise RuntimeError('teams_inbound_conversation_id_missing')
        conversa = obter_conversa(db, conversation_id, tenant_id=tenant_id or None)
        if (conversa.teams_destino_id or '').strip() != usuario_aad_object_id:
            registrar_evento(
                db,
                correlation_id,
                'teams-bot-user',
                'AI_CONVERSATION_TEAMS_REPLY_DENIED',
                'ai_conversation',
                conversation_id,
            )
            raise RuntimeError('teams_inbound_sender_mismatch')
    else:
        conversa = _conversa_recente(
            db,
            usuario_aad_object_id=usuario_aad_object_id,
            tenant_id=tenant_id,
            teams_chat_area_id=teams_chat_area_id,
        ) or _criar_conversa_teams(
            db,
            mensagem=mensagem,
            usuario_aad_object_id=usuario_aad_object_id,
            tenant_id=tenant_id,
            teams_chat_area_id=teams_chat_area_id,
            correlation_id=correlation_id,
        )

    result = executar_turno(
        db,
        conversa=conversa,
        mensagem=mensagem,
        correlation_id=correlation_id,
        idempotency_key=f'teams-activity:{activity_id}' if activity_id else None,
        origem='teams',
        enviar_teams=False,
    )
    if not result['duplicado']:
        await _responder_no_chat(
            db,
            usuario_aad_object_id=usuario_aad_object_id,
            resposta=result['mensagem_assistente'].content,
            activity_id=activity_id,
        )
    registrar_evento(
        db,
        correlation_id,
        'teams-bot-user',
        'AI_CONVERSATION_TEAMS_MESSAGE_COMPLETED',
        'ai_conversation',
        conversa.id,
        payload_minimo=json.dumps(
            {
                'channel': 'teams_bot',
                'duplicate': bool(result['duplicado']),
                'latency_ms': max(0, int((time.perf_counter() - started) * 1000)),
                'response_sent': not result['duplicado'],
                'status': 'completed',
            },
            separators=(',', ':'),
            sort_keys=True,
        ),
    )
    return {
        'processado': True,
        'conversation_id': conversa.id,
        'duplicado': result['duplicado'],
        'correlation_id': correlation_id,
    }


async def processar_activity_teams_bot_background(activity: dict[str, Any]) -> None:
    db = SessionLocal()
    started = time.perf_counter()
    try:
        await processar_activity_teams_bot(db, activity)
    except AIConversationError as exc:
        logger.warning('teams_inbound_ai_failed category=%s', type(exc).__name__)
        _registrar_falha_sanitizada(db, activity, exc, started=started)
        await _notificar_falha_sanitizada(db, activity)
    except Exception as exc:
        logger.warning('teams_inbound_failed category=%s', type(exc).__name__)
        _registrar_falha_sanitizada(db, activity, exc, started=started)
        await _notificar_falha_sanitizada(db, activity)
    finally:
        db.close()


def _registrar_falha_sanitizada(
    db: Session,
    activity: dict[str, Any],
    exc: Exception,
    *,
    started: float,
) -> None:
    value = activity.get('value') or {}
    supplied_correlation_id = value.get('correlation_id') if isinstance(value, dict) else None
    correlation_id = resolver_correlation_id(str(supplied_correlation_id or '').strip() or None, None)
    try:
        registrar_evento(
            db,
            correlation_id,
            'teams-bot-runtime',
            'AI_CONVERSATION_TEAMS_MESSAGE_FAILED',
            'ai_conversation',
            'background',
            payload_minimo=json.dumps(
                {
                    'channel': 'teams_bot',
                    'error_category': type(exc).__name__,
                    'latency_ms': max(0, int((time.perf_counter() - started) * 1000)),
                    'status': 'failed',
                },
                separators=(',', ':'),
                sort_keys=True,
            ),
        )
    except SQLAlchemyError as audit_exc:
        db.rollback()
        logger.warning(
            'teams_inbound_failure_audit_failed category=%s',
            type(audit_exc).__name__,
        )


async def _notificar_falha_sanitizada(db: Session, activity: dict[str, Any]) -> None:
    usuario_aad_object_id = str((activity.get('from') or {}).get('aadObjectId') or '').strip()
    if not usuario_aad_object_id:
        return
    try:
        await _responder_no_chat(
            db,
            usuario_aad_object_id=usuario_aad_object_id,
            resposta=(
                'Não consegui processar esta mensagem agora. '
                'Tente novamente em alguns instantes.'
            ),
            activity_id=str(activity.get('id') or '').strip(),
        )
    except Exception as exc:
        logger.warning('teams_inbound_failure_notice_failed category=%s', type(exc).__name__)
