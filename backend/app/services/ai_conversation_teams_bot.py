from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_conversation import AIConversation
from app.models.bot_conversa_referencia import BotConversaReferencia
from app.services.ai_conversation import construir_adaptive_card
from app.services.teams_gateway import (
    _enviar_atividade_bot_framework,
    obter_conversa_referencia_bot,
)


class AITeamsBotDeliveryError(RuntimeError):
    pass


def _destino_aad(conversa: AIConversation) -> str:
    return (
        (conversa.teams_destino_id or '').strip()
        or os.getenv('AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID', '').strip()
    )


def resolver_destino_bot(db: Session, conversa: AIConversation) -> str | None:
    """Resolve destino sem escolher silenciosamente entre vários usuários."""
    explicit = _destino_aad(conversa)
    if explicit:
        return explicit

    referencias = list(
        db.execute(
            select(BotConversaReferencia).where(
                BotConversaReferencia.channel_id == 'msteams'
            )
        ).scalars().all()
    )
    if len(referencias) == 1:
        return referencias[0].usuario_aad_object_id
    return None


async def enviar_cartao_conversa_bot(
    db: Session,
    *,
    conversa: AIConversation,
    resposta: str,
    correlation_id: str,
) -> dict[str, Any]:
    """Envia Adaptive Card diretamente ao chat 1:1 já conhecido do Bot Framework."""
    if not settings.teams_bot_configurado:
        raise AITeamsBotDeliveryError(
            'Bot do Teams não configurado para entrega bidirecional.'
        )

    usuario_aad = resolver_destino_bot(db, conversa)
    if not usuario_aad:
        raise AITeamsBotDeliveryError(
            'Não foi possível resolver de forma inequívoca o usuário Teams de destino.'
        )

    referencia = obter_conversa_referencia_bot(db, usuario_aad)
    if referencia is None:
        raise AITeamsBotDeliveryError(
            'O bot ainda não possui conversationReference para o usuário Teams.'
        )

    card = construir_adaptive_card(
        conversa,
        resposta,
        correlation_id=correlation_id,
    )
    url = (
        f"{referencia.service_url.rstrip('/')}"
        f'/v3/conversations/{referencia.conversation_id}/activities'
    )
    payload = {
        'type': 'message',
        'from': {'id': settings.teams_bot_app_id},
        'conversation': {'id': referencia.conversation_id},
        'text': f'{conversa.provider}/{conversa.model}: resposta concluída.',
        'attachments': [
            {
                'contentType': 'application/vnd.microsoft.card.adaptive',
                'content': card,
            }
        ],
    }

    provider = await _enviar_atividade_bot_framework(url, payload)
    conversa.teams_destino_tipo = 'chat_1a1'
    conversa.teams_destino_id = usuario_aad
    conversa.teams_modo = 'bot'
    db.commit()
    db.refresh(conversa)
    return {
        'entregue': True,
        'canal_usado': 'bot',
        'message_id': provider.get('id'),
        'chat_id': referencia.conversation_id,
        'usuario_aad_object_id': usuario_aad,
    }
