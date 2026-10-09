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
    settings = SimpleNamespace(teams_bot_configurado=False, teams_bot_app_id='bot-id', teams_bot_app_tenant_id='tenant-id')

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
    settings = SimpleNamespace(teams_bot_configurado=True, teams_bot_app_id='bot-id', teams_bot_app_tenant_id='tenant-id')

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
    settings = SimpleNamespace(teams_bot_configurado=True, teams_bot_app_id='bot-id', teams_bot_app_tenant_id='tenant-id')

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


def test_enviar_cartao_conserva_destinatario_resolvido_apos_erro_do_conector():
    db = MagicMock()
    conversa = _conversa(None)
    settings = SimpleNamespace(teams_bot_configurado=True, teams_bot_app_id='bot-id', teams_bot_app_tenant_id='tenant-id')
    referencia = SimpleNamespace(
        service_url='https://connector.invalid/',
        conversation_id='conversation-1',
        bot_id='bot-id',
        tenant_id='tenant-id',
    )
    provider = AsyncMock(side_effect=RuntimeError('falha simulada do transporte'))

    with (
        patch('app.services.ai_conversation_teams_bot.settings', settings),
        patch(
            'app.services.ai_conversation_teams_bot.resolver_destino_bot',
            return_value='aad-unico',
        ),
        patch(
            'app.services.ai_conversation_teams_bot.obter_conversa_referencia_bot',
            return_value=referencia,
        ),
        patch('app.services.ai_conversation_teams_bot._enviar_atividade_bot_framework', provider),
    ):
        with pytest.raises(AITeamsBotDeliveryError, match='provider_exception_runtimeerror'):
            asyncio.run(
                enviar_cartao_conversa_bot(
                    db, conversa=conversa, resposta='Resposta', correlation_id='corr-fallback'
                )
            )

    assert conversa.teams_destino_id == 'aad-unico'
    provider.assert_awaited_once()
    db.commit.assert_not_called()


def test_enviar_cartao_bloqueia_destinatario_ambiguo_antes_do_conector():
    db = MagicMock()
    conversa = _conversa(None)
    settings = SimpleNamespace(teams_bot_configurado=True, teams_bot_app_id='bot-id', teams_bot_app_tenant_id='tenant-id')
    provider = AsyncMock()

    with (
        patch('app.services.ai_conversation_teams_bot.settings', settings),
        patch('app.services.ai_conversation_teams_bot.resolver_destino_bot', return_value=None),
        patch('app.services.ai_conversation_teams_bot._enviar_atividade_bot_framework', provider),
    ):
        with pytest.raises(AITeamsBotDeliveryError, match='inequívoca'):
            asyncio.run(
                enviar_cartao_conversa_bot(
                    db, conversa=conversa, resposta='Resposta', correlation_id='corr-ambiguo'
                )
            )

    assert conversa.teams_destino_id is None
    provider.assert_not_awaited()
    db.commit.assert_not_called()


def test_enviar_cartao_bot_entrega_adaptive_card_e_vincula_conversa():
    db = MagicMock()
    conversa = _conversa()
    settings = SimpleNamespace(teams_bot_configurado=True, teams_bot_app_id='bot-id', teams_bot_app_tenant_id='tenant-id')
    referencia = SimpleNamespace(
        service_url='https://smba.trafficmanager.net/br/',
        conversation_id='a:teams-conv-1',
        bot_id='bot-id',
        tenant_id='tenant-id',
    )
    provider = AsyncMock(return_value={'id': 'teams-message-1', 'status_code': 202})

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
        'status_code': 202,
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


def test_enviar_cartao_bloqueia_referencia_de_outro_tenant_antes_do_conector():
    db = MagicMock()
    conversa = _conversa()
    settings = SimpleNamespace(
        teams_bot_configurado=True,
        teams_bot_app_id='bot-id',
        teams_bot_app_tenant_id='tenant-id',
    )
    referencia = SimpleNamespace(
        service_url='https://connector.invalid/',
        conversation_id='conversation-1',
        bot_id='bot-id',
        tenant_id='outro-tenant-sensivel',
    )
    provider = AsyncMock()

    with (
        patch('app.services.ai_conversation_teams_bot.settings', settings),
        patch('app.services.ai_conversation_teams_bot.resolver_destino_bot', return_value='aad-user-1'),
        patch('app.services.ai_conversation_teams_bot.obter_conversa_referencia_bot', return_value=referencia),
        patch('app.services.ai_conversation_teams_bot._enviar_atividade_bot_framework', provider),
    ):
        with pytest.raises(AITeamsBotDeliveryError, match='conversation_reference_tenant_id_mismatch'):
            asyncio.run(
                enviar_cartao_conversa_bot(
                    db, conversa=conversa, resposta='Resposta', correlation_id='corr-owner'
                )
            )

    provider.assert_not_awaited()
    db.commit.assert_not_called()
