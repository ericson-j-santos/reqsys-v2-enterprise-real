from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bot_conversa_referencia import BotConversaReferencia
from app.services.ai_conversation import _env_value, status_provedores


def _mascarar_identificador(value: str | None) -> str | None:
    normalized = (value or '').strip()
    if not normalized:
        return None
    if len(normalized) <= 8:
        return '***'
    return f'***{normalized[-8:]}'


def avaliar_prontidao_ai_teams(
    db: Session,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Avalia pré-condições para o aceite bidirecional IA -> Teams -> IA."""
    providers = status_provedores(env)
    providers_configurados = sorted(
        provider
        for provider, state in providers.items()
        if state.get('configurado') is True
    )

    referencias = list(
        db.execute(
            select(BotConversaReferencia).where(
                BotConversaReferencia.channel_id == 'msteams'
            )
        ).scalars().all()
    )
    referencias_por_usuario = {
        (ref.usuario_aad_object_id or '').strip(): ref
        for ref in referencias
        if (ref.usuario_aad_object_id or '').strip()
    }

    destino_explicito = _env_value(
        env,
        'AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID',
    )
    destino_resolvido: str | None = None
    origem_destino: str | None = None
    destino_tem_referencia = False

    if destino_explicito:
        destino_resolvido = destino_explicito
        origem_destino = 'configuracao_ambiente'
        destino_tem_referencia = destino_explicito in referencias_por_usuario
    elif len(referencias_por_usuario) == 1:
        destino_resolvido = next(iter(referencias_por_usuario))
        origem_destino = 'unica_conversation_reference'
        destino_tem_referencia = True

    bloqueios: list[dict[str, str]] = []
    if not settings.teams_bot_configurado:
        bloqueios.append(
            {
                'codigo': 'TEAMS_BOT_NAO_CONFIGURADO',
                'acao': 'Configurar TEAMS_BOT_APP_ID, TEAMS_BOT_APP_TENANT_ID e TEAMS_BOT_SECRET.',
            }
        )
    if not providers_configurados:
        bloqueios.append(
            {
                'codigo': 'PROVEDOR_IA_NAO_CONFIGURADO',
                'acao': 'Configurar ao menos um provedor de IA suportado no ambiente.',
            }
        )
    if not referencias_por_usuario:
        bloqueios.append(
            {
                'codigo': 'CONVERSATION_REFERENCE_AUSENTE',
                'acao': 'Instalar ou iniciar o bot no Teams para registrar a conversationReference.',
            }
        )
    elif destino_explicito and not destino_tem_referencia:
        bloqueios.append(
            {
                'codigo': 'DESTINATARIO_SEM_CONVERSATION_REFERENCE',
                'acao': 'Iniciar o bot no Teams com o usuário AAD configurado como destinatário.',
            }
        )
    elif not destino_explicito and len(referencias_por_usuario) > 1:
        bloqueios.append(
            {
                'codigo': 'DESTINATARIO_AMBIGUO',
                'acao': 'Definir AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID para selecionar o destinatário.',
            }
        )

    return {
        'schema_version': '1.0.0',
        'status': 'ready' if not bloqueios else 'blocked',
        'ready': not bloqueios,
        'checks': {
            'teams_bot_configurado': settings.teams_bot_configurado,
            'provedor_ia_configurado': bool(providers_configurados),
            'conversation_reference_disponivel': bool(referencias_por_usuario),
            'destinatario_inequivoco': destino_resolvido is not None,
            'destinatario_possui_conversation_reference': destino_tem_referencia,
        },
        'providers_configurados': providers_configurados,
        'conversation_references': len(referencias_por_usuario),
        'destinatario': {
            'origem': origem_destino,
            'aad_object_id_masked': _mascarar_identificador(destino_resolvido),
        },
        'bot_messaging_endpoint': '/v1/teams-gateway/ai-conversations/bot/messages',
        'bloqueios': bloqueios,
    }
