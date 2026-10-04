"""Testes de caminhos críticos — mensageria Teams via Microsoft Graph API (hub_lowcode)."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_teams_graph_service.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.core.identity_governance import IdentityGovernanceError  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.services import hub_lowcode as svc  # noqa: E402


@pytest.fixture(scope='module', autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _reset_circuit():
    svc.reset_teams_graph_circuit_breaker()
    yield
    svc.reset_teams_graph_circuit_breaker()


def _run(coro):
    return asyncio.run(coro)


def _identity_mock():
    identity = MagicMock()
    identity.evidence.return_value = {
        'profile_name': 'reqsys-test-teams-confidential',
        'environment': 'test',
        'purpose': 'teams-proactive-messaging',
        'data_classification': 'confidential',
        'client_id_suffix': '12345678',
        'rotation_due_at': '2099-01-01T00:00:00+00:00',
        'rotation_required': False,
    }
    return identity


def _mock_credenciais_graph(monkeypatch):
    async def _token():
        return 'tok-governado', _identity_mock()

    monkeypatch.setattr(svc, 'acquire_teams_graph_token', _token)
    monkeypatch.setattr(
        svc,
        'teams_graph_identity_status',
        lambda: {'configured': True, **_identity_mock().evidence()},
    )


def _mock_identidade_graph_ausente(monkeypatch):
    async def _token():
        raise IdentityGovernanceError('REQSYS_IDENTITY_GOVERNANCE_FILE não configurado; seleção de identidade bloqueada.')

    monkeypatch.setattr(svc, 'acquire_teams_graph_token', _token)
    monkeypatch.setattr(
        svc,
        'teams_graph_identity_status',
        lambda: {
            'configured': False,
            'purpose': 'teams-proactive-messaging',
            'data_classification': 'confidential',
            'error': 'identidade governada não configurada',
        },
    )


def _mock_httpx_post_sequence(mock_client_cls, *respostas):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=list(respostas))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client
    return mock_client


def _mock_httpx_get_sequence(mock_client_cls, *respostas):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=list(respostas))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client
    return mock_client


def _resp(status_code=200, json_data=None, raise_error=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = str(json_data)
    mock_resp.json.return_value = json_data or {}
    if raise_error:
        mock_resp.raise_for_status = MagicMock(side_effect=raise_error)
    else:
        mock_resp.raise_for_status = MagicMock()
    return mock_resp


def test_enviar_mensagem_chat_sem_identidade_governada_degrada(monkeypatch):
    _mock_identidade_graph_ausente(monkeypatch)

    resultado = _run(svc.enviar_mensagem_chat_teams('chat-1', 'ola'))

    assert resultado['configurado'] is False
    assert resultado['enviado'] is False
    assert 'IDENTITY_GOVERNANCE' in resultado['erro']


def test_enviar_mensagem_chat_sem_chat_id(monkeypatch):
    _mock_credenciais_graph(monkeypatch)
    resultado = _run(svc.enviar_mensagem_chat_teams('', 'ola'))
    assert resultado['configurado'] is True
    assert resultado['enviado'] is False
    assert 'chat_id' in resultado['erro']


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_enviar_mensagem_chat_sucesso_registra_log(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)
    _mock_httpx_post_sequence(
        mock_client_cls,
        _resp(status_code=201, json_data={'id': 'msg-123'}),
    )

    db = SessionLocal()
    try:
        resultado = _run(svc.enviar_mensagem_chat_teams('chat-1', 'Ola time', db=db, autor='qa'))
    finally:
        db.close()

    assert resultado['configurado'] is True
    assert resultado['enviado'] is True
    assert resultado['message_id'] == 'msg-123'
    assert resultado['identity']['profile_name'] == 'reqsys-test-teams-confidential'

    db = SessionLocal()
    try:
        historico = svc.listar_historico_integracoes(db, tipo='teams_graph')
    finally:
        db.close()
    assert historico['total'] >= 1
    assert historico['eventos'][0]['status'] == 'sucesso'


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_enviar_mensagem_chat_http_error_nao_retenta(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)
    erro_http = httpx.HTTPStatusError('forbidden', request=MagicMock(), response=_resp(status_code=403, json_data={}))
    mock_client = _mock_httpx_post_sequence(
        mock_client_cls,
        MagicMock(raise_for_status=MagicMock(side_effect=erro_http)),
    )

    resultado = _run(svc.enviar_mensagem_chat_teams('chat-1', 'ola'))

    assert resultado['enviado'] is False
    assert 'HTTP 403' in resultado['erro']
    assert mock_client.post.call_count == 1


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_criar_chat_individual_sem_identidade_governada_degrada(mock_client_cls, monkeypatch):
    _mock_identidade_graph_ausente(monkeypatch)

    resultado = _run(svc.criar_chat_individual_teams('user-a', 'user-b'))

    assert resultado['configurado'] is False
    assert resultado['ok'] is False
    mock_client_cls.assert_not_called()


def test_criar_chat_individual_exige_dois_usuarios(monkeypatch):
    _mock_credenciais_graph(monkeypatch)
    resultado = _run(svc.criar_chat_individual_teams('user-a', ''))
    assert resultado['configurado'] is True
    assert resultado['ok'] is False
    assert 'obrigatórios' in resultado['erro']


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_criar_chat_individual_entre_dois_usuarios_reais(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)
    _mock_httpx_post_sequence(
        mock_client_cls,
        _resp(status_code=201, json_data={'id': 'chat-999'}),
    )

    resultado = _run(svc.criar_chat_individual_teams('user-a', 'user-b'))

    assert resultado['ok'] is True
    assert resultado['chat_id'] == 'chat-999'
    assert resultado['identity']['profile_name'] == 'reqsys-test-teams-confidential'


def test_enviar_mensagem_como_usuario_sem_token(monkeypatch):
    resultado = _run(svc.enviar_mensagem_chat_teams_como_usuario('chat-1', 'ola', ''))
    assert resultado['enviado'] is False
    assert 'usuario_access_token' in resultado['erro']


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_enviar_mensagem_como_usuario_sucesso_nao_usa_identidade_app_only(mock_client_cls, monkeypatch):
    _mock_httpx_post_sequence(mock_client_cls, _resp(status_code=201, json_data={'id': 'msg-delegado-1'}))

    db = SessionLocal()
    try:
        resultado = _run(svc.enviar_mensagem_chat_teams_como_usuario(
            'chat-1', 'Ola delegado', 'user-delegated-token', db=db, autor='qa',
        ))
    finally:
        db.close()

    assert resultado['enviado'] is True
    assert resultado['message_id'] == 'msg-delegado-1'
    assert mock_client_cls.return_value.post.call_count == 1


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_criar_chat_e_enviar_como_usuario_fluxo_completo(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)

    _mock_httpx_post_sequence(
        mock_client_cls,
        _resp(status_code=201, json_data={'id': 'chat-999'}),
        _resp(status_code=201, json_data={'id': 'msg-1'}),
    )

    resultado = _run(svc.criar_chat_e_enviar_como_usuario('user-a', 'user-b', 'Ola direto', 'user-delegated-token'))

    assert resultado['enviado'] is True
    assert resultado['chat_id'] == 'chat-999'
    assert resultado['message_id'] == 'msg-1'
    assert resultado['identity']['profile_name'] == 'reqsys-test-teams-confidential'


def test_listar_chats_como_usuario_sem_token():
    resultado = _run(svc.listar_chats_como_usuario(''))
    assert resultado['chats'] == []
    assert 'usuario_access_token' in resultado['erro']


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_listar_chats_como_usuario_sucesso(mock_client_cls):
    _mock_httpx_get_sequence(mock_client_cls, _resp(json_data={
        'value': [
            {
                'id': 'chat-1',
                'topic': None,
                'chatType': 'oneOnOne',
                'members': [
                    {'userId': 'user-eu', 'displayName': 'Ericson', 'email': 'ericson@tieri659.onmicrosoft.com'},
                    {'userId': 'user-outro', 'displayName': 'Outro Usuario', 'email': 'outro@tieri659.onmicrosoft.com'},
                ],
            },
            {
                'id': 'chat-2',
                'topic': 'Squad ReqSys',
                'chatType': 'group',
                'members': [
                    {'userId': 'user-eu', 'displayName': 'Ericson', 'email': 'ericson@tieri659.onmicrosoft.com'},
                    {'userId': 'user-a', 'displayName': 'Fulano', 'email': 'fulano@tieri659.onmicrosoft.com'},
                    {'userId': 'user-b', 'displayName': 'Ciclano', 'email': 'ciclano@tieri659.onmicrosoft.com'},
                ],
            },
        ],
    }))

    resultado = _run(svc.listar_chats_como_usuario('user-delegated-token'))

    assert 'erro' not in resultado
    assert len(resultado['chats']) == 2
    assert resultado['chats'][0]['id'] == 'chat-1'
    assert resultado['chats'][0]['tipo'] == 'oneOnOne'
    assert len(resultado['chats'][0]['membros']) == 2
    assert resultado['chats'][1]['topico'] == 'Squad ReqSys'


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_listar_chats_como_usuario_http_error(mock_client_cls):
    erro_http = httpx.HTTPStatusError('unauthorized', request=MagicMock(), response=_resp(status_code=401, json_data={}))
    _mock_httpx_get_sequence(mock_client_cls, MagicMock(raise_for_status=MagicMock(side_effect=erro_http)))

    resultado = _run(svc.listar_chats_como_usuario('token-expirado'))

    assert resultado['chats'] == []
    assert 'HTTP 401' in resultado['erro']
