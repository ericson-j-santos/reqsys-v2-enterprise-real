from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import ai_conversation as api
from app.core.service_tokens import ServiceAuthContext
from app.db import get_db
from app.main import app
from app.services import ai_conversation_readiness as readiness

client = TestClient(app)


def _db_com_referencias(*usuarios: str):
    db = MagicMock()
    refs = [SimpleNamespace(usuario_aad_object_id=user) for user in usuarios]
    db.execute.return_value.scalars.return_value.all.return_value = refs
    return db


def _settings(bot_configurado: bool):
    return SimpleNamespace(teams_bot_configurado=bot_configurado)


def test_readiness_ready_com_bot_provider_e_unica_referencia(monkeypatch):
    db = _db_com_referencias('aad-user-123456789')
    monkeypatch.setattr(readiness, 'settings', _settings(True))

    result = readiness.avaliar_prontidao_ai_teams(
        db,
        env={'AI_CONVERSATION_OPENAI_API_KEY': 'fake-key'},
    )

    assert result['status'] == 'ready'
    assert result['ready'] is True
    assert result['bloqueios'] == []
    assert result['providers_configurados'] == ['openai']
    assert result['conversation_references'] == 1
    assert result['checks'] == {
        'teams_bot_configurado': True,
        'provedor_ia_configurado': True,
        'conversation_reference_disponivel': True,
        'destinatario_inequivoco': True,
        'destinatario_possui_conversation_reference': True,
    }
    assert result['destinatario']['origem'] == 'unica_conversation_reference'
    assert result['destinatario']['aad_object_id_masked'].startswith('***')
    assert 'aad-user-123456789' not in str(result)


def test_readiness_bloqueia_bot_provider_e_reference_ausentes(monkeypatch):
    db = _db_com_referencias()
    monkeypatch.setattr(readiness, 'settings', _settings(False))

    result = readiness.avaliar_prontidao_ai_teams(db, env={})

    assert result['ready'] is False
    assert result['status'] == 'blocked'
    codigos = {item['codigo'] for item in result['bloqueios']}
    assert codigos == {
        'TEAMS_BOT_NAO_CONFIGURADO',
        'PROVEDOR_IA_NAO_CONFIGURADO',
        'CONVERSATION_REFERENCE_AUSENTE',
    }


def test_readiness_bloqueia_multiplos_destinatarios_sem_selecao(monkeypatch):
    db = _db_com_referencias('aad-user-1', 'aad-user-2')
    monkeypatch.setattr(readiness, 'settings', _settings(True))

    result = readiness.avaliar_prontidao_ai_teams(
        db,
        env={'AI_CONVERSATION_GEMINI_API_KEY': 'fake-key'},
    )

    assert result['ready'] is False
    assert result['checks']['conversation_reference_disponivel'] is True
    assert result['checks']['destinatario_inequivoco'] is False
    assert [item['codigo'] for item in result['bloqueios']] == ['DESTINATARIO_AMBIGUO']


def test_readiness_destino_explicito_precisa_ter_reference(monkeypatch):
    db = _db_com_referencias('aad-owner')
    monkeypatch.setattr(readiness, 'settings', _settings(True))

    result = readiness.avaliar_prontidao_ai_teams(
        db,
        env={
            'AI_CONVERSATION_OPENAI_API_KEY': 'fake-key',
            'AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID': 'aad-sem-reference',
        },
    )

    assert result['ready'] is False
    assert result['destinatario']['origem'] == 'configuracao_ambiente'
    assert result['checks']['destinatario_inequivoco'] is True
    assert result['checks']['destinatario_possui_conversation_reference'] is False
    assert [item['codigo'] for item in result['bloqueios']] == [
        'DESTINATARIO_SEM_CONVERSATION_REFERENCE'
    ]


def test_readiness_destino_explicito_com_reference_fica_ready(monkeypatch):
    db = _db_com_referencias('aad-owner', 'aad-outro')
    monkeypatch.setattr(readiness, 'settings', _settings(True))

    result = readiness.avaliar_prontidao_ai_teams(
        db,
        env={
            'AI_CONVERSATION_CLAUDE_API_KEY': 'fake-key',
            'AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID': 'aad-owner',
        },
    )

    assert result['ready'] is True
    assert result['providers_configurados'] == ['claude']
    assert result['destinatario']['origem'] == 'configuracao_ambiente'


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (None, None),
        ('', None),
        ('12345678', '***'),
        ('123456789', '***23456789'),
    ],
)
def test_mask_identificador_nao_expoe_valor_completo(value, expected):
    assert readiness._mascarar_identificador(value) == expected


@pytest.fixture
def readiness_api_override():
    db = MagicMock()
    app.dependency_overrides[api.require_ai_conversation_auth] = lambda: ServiceAuthContext(
        ator='admin@teste',
        via_token=False,
    )
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(api.require_ai_conversation_auth, None)
    app.dependency_overrides.pop(get_db, None)


def test_readiness_endpoint_retorna_evidencia_estruturada(
    readiness_api_override,
    monkeypatch,
):
    expected = {
        'schema_version': '1.0.0',
        'status': 'ready',
        'ready': True,
        'checks': {'teams_bot_configurado': True},
        'providers_configurados': ['openai'],
        'conversation_references': 1,
        'destinatario': {
            'origem': 'unica_conversation_reference',
            'aad_object_id_masked': '***12345678',
        },
        'bot_messaging_endpoint': '/v1/teams-gateway/ai-conversations/bot/messages',
        'bloqueios': [],
    }
    avaliar = MagicMock(return_value=expected)
    monkeypatch.setattr(api, 'avaliar_prontidao_ai_teams', avaliar)

    response = client.get('/v1/teams-gateway/ai-conversations/readiness')

    assert response.status_code == 200
    assert response.json()['data'] == expected
    avaliar.assert_called_once_with(readiness_api_override)
