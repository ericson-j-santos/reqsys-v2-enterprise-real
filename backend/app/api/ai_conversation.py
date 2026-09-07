from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.service_tokens import ServiceAuthContext, require_admin_or_service_token
from app.db import get_db
from app.schemas.ai_conversation import AIConversationCreateRequest, AIConversationReplyRequest
from app.services.ai_conversation import (
    AIConversationConflictError,
    AIConversationError,
    AIConversationNotFoundError,
    AIProviderConfigurationError,
    AIProviderExecutionError,
    _enfileirar_teams,
    criar_conversa,
    executar_turno,
    obter_conversa,
    serializar_conversa,
    status_provedores,
)
from app.services.ai_conversation_teams_bot import (
    AITeamsBotDeliveryError,
    enviar_cartao_conversa_bot,
)
from app.services.auditoria import registrar_evento
from app.services.teams_gateway import (
    salvar_conversa_referencia_bot,
    validar_jwt_bot_framework,
)
from app.services.teams_notifications import executar_item_fila, serializar_item

logger = logging.getLogger('reqsys.ai_conversation_api')

router = APIRouter(prefix='/ai-conversations', tags=['Central de Conversas de IA'])
require_ai_conversation_auth = require_admin_or_service_token(
    'teams_gateway:ai_conversations'
)


def _http_error(exc: AIConversationError) -> HTTPException:
    if isinstance(exc, AIConversationNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, AIConversationConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, AIProviderConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, AIProviderExecutionError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(
        status_code=500,
        detail='Falha interna na Central de Conversas de IA.',
    )


async def _entregar_resposta_teams(
    db: Session,
    *,
    conversa,
    resposta: str,
    correlation_id: str,
    habilitado: bool,
):
    if not habilitado:
        return None

    try:
        direct = await enviar_cartao_conversa_bot(
            db,
            conversa=conversa,
            resposta=resposta,
            correlation_id=correlation_id,
        )
        return {'modo': 'bot_adaptive_card', 'entrega': direct, 'fila': None}
    except AITeamsBotDeliveryError as exc:
        logger.info(
            'ai_conversation_bot_direct_unavailable conversation_id=%s reason=%s',
            conversa.id,
            exc,
        )
    except Exception as exc:
        logger.warning(
            'ai_conversation_bot_direct_failed conversation_id=%s error=%s',
            conversa.id,
            type(exc).__name__,
        )

    item = _enfileirar_teams(
        db,
        conversa=conversa,
        resposta=resposta,
        correlation_id=correlation_id,
    )
    item = await executar_item_fila(db, item)
    return {
        'modo': 'fila_gateway',
        'entrega': None,
        'fila': serializar_item(item),
    }


@router.get('/status')
def ai_conversations_status(
    _ctx: ServiceAuthContext = Depends(require_ai_conversation_auth),
):
    return ok(
        {
            'schema_version': '1.1.0',
            'providers': status_provedores(),
            'teams_reply_contract': {
                'action': 'ai_conversation_reply',
                'input_field': 'mensagem',
                'bot_messaging_endpoint': (
                    '/v1/teams-gateway/ai-conversations/bot/messages'
                ),
                'service_token_scope': 'teams_gateway:ai_conversations',
            },
        }
    )


@router.post('')
async def ai_conversations_create(
    payload: AIConversationCreateRequest,
    ctx: ServiceAuthContext = Depends(require_ai_conversation_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    conversa = criar_conversa(db, payload, correlation_id=correlation_id)
    registrar_evento(
        db,
        correlation_id,
        ctx.ator,
        'AI_CONVERSATION_CREATED',
        'ai_conversation',
        conversa.id,
    )

    try:
        result = executar_turno(
            db,
            conversa=conversa,
            mensagem=payload.mensagem,
            correlation_id=correlation_id,
            idempotency_key=payload.idempotency_key,
            origem=payload.origem,
            enviar_teams=False,
        )
    except AIConversationError as exc:
        registrar_evento(
            db,
            correlation_id,
            ctx.ator,
            'AI_CONVERSATION_TURN_FAILED',
            'ai_conversation',
            conversa.id,
        )
        raise _http_error(exc) from None

    teams = await _entregar_resposta_teams(
        db,
        conversa=conversa,
        resposta=result['mensagem_assistente'].content,
        correlation_id=correlation_id,
        habilitado=payload.enviar_teams,
    )
    registrar_evento(
        db,
        correlation_id,
        ctx.ator,
        'AI_CONVERSATION_RESPONSE_COMPLETED',
        'ai_conversation',
        conversa.id,
    )
    return ok(
        {
            'conversation': serializar_conversa(db, conversa),
            'response': result['mensagem_assistente'].content,
            'duplicate': result['duplicado'],
            'teams': teams,
        },
        correlation_id,
    )


@router.get('/{conversation_id}')
def ai_conversations_get(
    conversation_id: str,
    _ctx: ServiceAuthContext = Depends(require_ai_conversation_auth),
    db: Session = Depends(get_db),
):
    try:
        conversa = obter_conversa(db, conversation_id)
    except AIConversationError as exc:
        raise _http_error(exc) from None
    return ok(serializar_conversa(db, conversa))


@router.post('/{conversation_id}/reply')
async def ai_conversations_reply(
    conversation_id: str,
    payload: AIConversationReplyRequest,
    ctx: ServiceAuthContext = Depends(require_ai_conversation_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        conversa = obter_conversa(db, conversation_id)
        result = executar_turno(
            db,
            conversa=conversa,
            mensagem=payload.mensagem,
            correlation_id=correlation_id,
            idempotency_key=payload.idempotency_key,
            origem=payload.origem,
            enviar_teams=False,
        )
    except AIConversationError as exc:
        registrar_evento(
            db,
            correlation_id,
            ctx.ator,
            'AI_CONVERSATION_REPLY_FAILED',
            'ai_conversation',
            conversation_id,
        )
        raise _http_error(exc) from None

    teams = await _entregar_resposta_teams(
        db,
        conversa=conversa,
        resposta=result['mensagem_assistente'].content,
        correlation_id=correlation_id,
        habilitado=payload.enviar_teams,
    )
    registrar_evento(
        db,
        correlation_id,
        ctx.ator,
        'AI_CONVERSATION_REPLY_COMPLETED',
        'ai_conversation',
        conversation_id,
    )
    return ok(
        {
            'conversation_id': conversation_id,
            'response': result['mensagem_assistente'].content,
            'duplicate': result['duplicado'],
            'teams': teams,
        },
        correlation_id,
    )


@router.post('/bot/messages')
async def ai_conversations_bot_messages(
    request: Request,
    db: Session = Depends(get_db),
):
    """Endpoint do Azure Bot que preserva o comportamento base e trata o cartão."""
    auth_header = request.headers.get('authorization', '')
    token = (
        auth_header[7:].strip()
        if auth_header.lower().startswith('bearer ')
        else ''
    )
    if not token:
        raise HTTPException(
            status_code=401,
            detail='Token do Bot Framework ausente',
        )

    try:
        validar_jwt_bot_framework(token)
    except Exception:
        logger.warning('ai_conversation_bot_token_invalido')
        raise HTTPException(
            status_code=401,
            detail='Token do Bot Framework invalido',
        ) from None

    activity = await request.json()
    remetente = activity.get('from') or {}
    usuario_aad_object_id = remetente.get('aadObjectId')
    service_url = activity.get('serviceUrl')
    teams_conversation_id = (activity.get('conversation') or {}).get('id')
    bot_id = (activity.get('recipient') or {}).get('id', '')
    tenant_id = (
        ((activity.get('channelData') or {}).get('tenant') or {}).get('id', '')
    )

    if usuario_aad_object_id and service_url and teams_conversation_id:
        salvar_conversa_referencia_bot(
            db,
            usuario_aad_object_id=usuario_aad_object_id,
            service_url=service_url,
            conversation_id=teams_conversation_id,
            bot_id=bot_id,
            tenant_id=tenant_id,
        )

    value = activity.get('value') or {}
    if not isinstance(value, dict) or value.get('reqsys_action') != 'ai_conversation_reply':
        return ok({'type': 'message', 'recebido': True, 'acao_ia': False})

    conversation_id = str(value.get('conversation_id') or '').strip()
    mensagem = str(value.get('mensagem') or activity.get('text') or '').strip()
    if not conversation_id or not mensagem:
        raise HTTPException(
            status_code=422,
            detail='conversation_id e mensagem são obrigatórios no cartão.',
        )

    activity_id = str(activity.get('id') or '').strip()
    correlation_id = resolver_correlation_id(
        str(value.get('correlation_id') or '').strip() or None,
        None,
    )

    try:
        conversa = obter_conversa(db, conversation_id)
        if usuario_aad_object_id:
            conversa.teams_destino_tipo = 'chat_1a1'
            conversa.teams_destino_id = usuario_aad_object_id
            conversa.teams_modo = 'bot'
            db.commit()
        result = executar_turno(
            db,
            conversa=conversa,
            mensagem=mensagem,
            correlation_id=correlation_id,
            idempotency_key=(
                f'teams-activity:{activity_id}'
                if activity_id
                else None
            ),
            origem='teams',
            enviar_teams=False,
        )
    except AIConversationError as exc:
        raise _http_error(exc) from None

    teams = await _entregar_resposta_teams(
        db,
        conversa=conversa,
        resposta=result['mensagem_assistente'].content,
        correlation_id=correlation_id,
        habilitado=True,
    )
    registrar_evento(
        db,
        correlation_id,
        'teams-bot-user',
        'AI_CONVERSATION_TEAMS_REPLY_COMPLETED',
        'ai_conversation',
        conversation_id,
    )
    return ok(
        {
            'type': 'message',
            'recebido': True,
            'acao_ia': True,
            'conversation_id': conversation_id,
            'duplicate': result['duplicado'],
            'teams': teams,
        },
        correlation_id,
    )
