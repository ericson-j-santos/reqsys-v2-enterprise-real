import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_conversation_teams_bot import (
    AITeamsBotDeliveryError,
    enviar_cartao_conversa_bot,
    resolver_destino_bot,
)


def _conversa(destino='aad-user-1'):
    return SimpleNamespace(
        id='conv-1',
        provider='openai',
        model='gpt-test',
        titulo='Conversa de teste',
        teams_destino_id=destino,
        teams_destino_tipo='chat_1a1',
        teams_modo='bot',
    )


def test_resolver_destino_bot_prioriza_destino_explicito():
    db = MagicMock()

    assert resolver_destino_bot(db, _conversa('aad-explicito')) == 'aad-explicito'
    db.execute.assert_not_called()


def test_resolver_destino_bot_usa_unica_referencia_quando_destino_ausente(monkeypatch):
    monkeypatch.delenv('AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID', raising=False)
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [
        SimpleNamespace(usuario_aad_object_id='aad-unico')
    ]

    assert resolver_destino_bot(db, _conversa(None)) == 'aad-unico'


def test_resolver_destino_bot_recusa_ambiguidade(monkeypatch):
    monkeypatch.delenv('AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID', raising=False)
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [
        SimpleNamespace(usuario_aad_object_id='aad-1'),
        SimpleNamespace(usuario_aad_object_id='aad-2'),
    ]

    assert resolver_destino_bot(db, _conversa(None)) is None


def test_enviar_cartao_exige_bot_configurado():
    db = MagicMock()
    settings = SimpleNamespace(teams_bot_configurado=False, teams_bot_app_id='bot-id')

    with patch('app.services.ai_conversation_teams_bot.settings', settings):
        with pytest.raises(AITeamsBotDeliveryError, match='não configurado'):
            asyncio.run(
                enviar_cartao_conversa_bot(
                    db,
                    conversa=_conversa(),
                    resposta='Resposta',
                    correlation_id='corr-1',
                )
            )


def test_enviar_cartao_exige_destinatario_inequivoco():
    db = MagicMock()
    settings = SimpleNamespace(teams_bot_configurado=True, teams_bot_app_id='bot-id')

    with (
        patch('app.services.ai_conversation_teams_bot.settings', settings),
        patch(
            'app.services.ai_conversation_teams_bot.resolver_destino_bot',
            return_value=None,
        ),
    ):
        with pytest.raises(AITeamsBotDeliveryError, match='inequívoca'):
            asyncio.run(
                enviar_cartao_conversa_bot(
                    db,
                    conversa=_conversa(None),
                    resposta='Resposta',
                    correlation_id='corr-2',
                )
            )


def test_enviar_cartao_exige_conversation_reference():
    db = MagicMock()
    settings = SimpleNamespace(teams_bot_configurado=True, teams_bot_app_id='bot-id')

    with (
        patch('app.services.ai_conversation_teams_bot.settings', settings),
        patch(
            'app.services.ai_conversation_teams_bot.resolver_destino_bot',
            return_value='aad-user-1',
        ),
        patch(
            'app.services.ai_conversation_teams_bot.obter_conversa_referencia_bot',
            return_value=None,
        ),
    ):
        with pytest.raises(AITeamsBotDeliveryError, match='conversationReference'):
            asyncio.run(
                enviar_cartao_conversa_bot(
                    db,
                    conversa=_conversa(),
                    resposta='Resposta',
                    correlation_id='corr-3',
                )
            )


def test_enviar_cartao_bot_entrega_adaptive_card_e_vincula_conversa():
    db = MagicMock()
    conversa = _conversa()
    settings = SimpleNamespace(teams_bot_configurado=True, teams_bot_app_id='bot-id')
    referencia = SimpleNamespace(
        service_url='https://smba.trafficmanager.net/br/',
        conversation_id='a:teams-conv-1',
    )
    provider = AsyncMock(return_value={'id': 'teams-message-1'})

    with (
        patch('app.services.ai_conversation_teams_bot.settings', settings),
        patch(
            'app.services.ai_conversation_teams_bot.resolver_destino_bot',
            return_value='aad-user-1',
        ),
        patch(
            'app.services.ai_conversation_teams_bot.obter_conversa_referencia_bot',
            return_value=referencia,
        ),
        patch(
            'app.services.ai_conversation_teams_bot._enviar_atividade_bot_framework',
            provider,
        ),
    ):
        result = asyncio.run(
            enviar_cartao_conversa_bot(
                db,
                conversa=conversa,
                resposta='Resposta concluída',
                correlation_id='corr-4',
            )
        )

    assert result == {
        'entregue': True,
        'canal_usado': 'bot',
        'message_id': 'teams-message-1',
        'chat_id': 'a:teams-conv-1',
        'usuario_aad_object_id': 'aad-user-1',
    }
    url, payload = provider.await_args.args
    assert url.endswith('/v3/conversations/a:teams-conv-1/activities')
    attachment = payload['attachments'][0]
    assert attachment['contentType'] == 'application/vnd.microsoft.card.adaptive'
    assert attachment['content']['actions'][0]['data']['conversation_id'] == 'conv-1'
    assert conversa.teams_destino_tipo == 'chat_1a1'
    assert conversa.teams_destino_id == 'aad-user-1'
    assert conversa.teams_modo == 'bot'
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(conversa)
