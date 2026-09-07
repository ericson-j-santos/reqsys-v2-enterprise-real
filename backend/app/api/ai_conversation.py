from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
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
    criar_conversa,
    executar_turno,
    obter_conversa,
    serializar_conversa,
    status_provedores,
)
from app.services.auditoria import registrar_evento
from app.services.teams_notifications import executar_item_fila, serializar_item

router = APIRouter(prefix='/ai-conversations', tags=['Central de Conversas de IA'])
require_ai_conversation_auth = require_admin_or_service_token('teams_gateway:ai_conversations')


def _http_error(exc: AIConversationError) -> HTTPException:
    if isinstance(exc, AIConversationNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, AIConversationConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, AIProviderConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, AIProviderExecutionError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail='Falha interna na Central de Conversas de IA.')


async def _entregar_teams(db: Session, notificacao):
    if notificacao is None:
        return None
    return await executar_item_fila(db, notificacao)


@router.get('/status')
def ai_conversations_status(
    _ctx: ServiceAuthContext = Depends(require_ai_conversation_auth),
):
    return ok(
        {
            'schema_version': '1.0.0',
            'providers': status_provedores(),
            'teams_reply_contract': {
                'action': 'ai_conversation_reply',
                'input_field': 'mensagem',
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
            enviar_teams=payload.enviar_teams,
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

    teams_item = await _entregar_teams(db, result['notificacao'])
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
            'teams': serializar_item(teams_item) if teams_item is not None else None,
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
            enviar_teams=payload.enviar_teams,
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

    teams_item = await _entregar_teams(db, result['notificacao'])
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
            'teams': serializar_item(teams_item) if teams_item is not None else None,
        },
        correlation_id,
    )
