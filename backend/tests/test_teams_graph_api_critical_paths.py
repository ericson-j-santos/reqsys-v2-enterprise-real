"""Caminhos críticos — API Teams via Graph API (hub_lowcode)."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_teams_graph_status_endpoint_sem_credenciais(monkeypatch):
    import app.api.hub_lowcode as api_mod

    monkeypatch.setattr(api_mod.settings, 'azure_tenant_id', '')
    monkeypatch.setattr(api_mod.settings, 'azure_client_id', '')
    monkeypatch.setattr(api_mod.settings, 'azure_client_secret', '')

    response = client.get('/v1/hub-lowcode/teams/graph/status')
    assert response.status_code == 200
    data = response.json()['data']
    assert data['envio_app_only_configurado'] is False
    assert data['semaforo'] == 'cinza'


@patch('app.api.hub_lowcode.enviar_mensagem_chat_teams', new_callable=AsyncMock)
def test_teams_graph_enviar_mensagem_chat_endpoint(mock_enviar):
    mock_enviar.return_value = {'configurado': True, 'enviado': True, 'message_id': 'msg-1', 'chat_id': 'chat-1'}
    response = client.post(
        '/v1/hub-lowcode/teams/graph/mensagens/chat',
        json={'chat_id': 'chat-1', 'texto': 'Ola time'},
    )
    assert response.status_code == 200
    assert response.json()['data']['enviado'] is True
    mock_enviar.assert_awaited_once()


@patch('app.api.hub_lowcode.enviar_mensagem_chat_teams_como_usuario', new_callable=AsyncMock)
def test_teams_graph_enviar_mensagem_chat_delegado_endpoint(mock_enviar):
    mock_enviar.return_value = {'enviado': True, 'message_id': 'msg-2', 'chat_id': 'chat-2'}
    response = client.post(
        '/v1/hub-lowcode/teams/graph/mensagens/chat-delegado',
        json={'chat_id': 'chat-2', 'texto': 'Ola delegado', 'usuario_access_token': 'fake-token'},
    )
    assert response.status_code == 200
    assert response.json()['data']['enviado'] is True
    mock_enviar.assert_awaited_once()


def test_teams_graph_enviar_mensagem_chat_delegado_endpoint_exige_token():
    response = client.post(
        '/v1/hub-lowcode/teams/graph/mensagens/chat-delegado',
        json={'chat_id': 'chat-2', 'texto': 'Ola delegado', 'usuario_access_token': ''},
    )
    assert response.status_code == 422


@patch('app.api.hub_lowcode.criar_chat_individual_teams', new_callable=AsyncMock)
def test_teams_graph_criar_chat_individual_endpoint(mock_criar):
    mock_criar.return_value = {'configurado': True, 'ok': True, 'chat_id': 'chat-3'}
    response = client.post(
        '/v1/hub-lowcode/teams/graph/chats/individual',
        json={'usuario_a_aad_object_id': 'user-a', 'usuario_b_aad_object_id': 'user-b'},
    )
    assert response.status_code == 200
    assert response.json()['data']['chat_id'] == 'chat-3'
    mock_criar.assert_awaited_once()


@patch('app.api.hub_lowcode.criar_chat_e_enviar_como_usuario', new_callable=AsyncMock)
def test_teams_graph_criar_chat_e_enviar_delegado_endpoint(mock_fluxo):
    mock_fluxo.return_value = {'enviado': True, 'chat_id': 'chat-4', 'message_id': 'msg-4'}
    response = client.post(
        '/v1/hub-lowcode/teams/graph/chats/individual/enviar-delegado',
        json={
            'usuario_a_aad_object_id': 'user-a',
            'usuario_b_aad_object_id': 'user-b',
            'texto': 'Ola',
            'usuario_access_token': 'fake-token',
        },
    )
    assert response.status_code == 200
    assert response.json()['data']['message_id'] == 'msg-4'
    mock_fluxo.assert_awaited_once()


def test_teams_graph_enviar_mensagem_chat_endpoint_valida_corpo():
    response = client.post('/v1/hub-lowcode/teams/graph/mensagens/chat', json={'chat_id': '', 'texto': ''})
    assert response.status_code == 422


@patch('app.api.hub_lowcode.listar_chats_como_usuario', new_callable=AsyncMock)
def test_teams_graph_listar_chats_endpoint(mock_listar):
    mock_listar.return_value = {'chats': [{'id': 'chat-1', 'topico': None, 'tipo': 'oneOnOne', 'membros': []}]}
    response = client.post(
        '/v1/hub-lowcode/teams/graph/chats',
        json={'usuario_access_token': 'fake-token'},
    )
    assert response.status_code == 200
    assert response.json()['data']['chats'][0]['id'] == 'chat-1'
    mock_listar.assert_awaited_once_with('fake-token', top=50)


def test_teams_graph_listar_chats_endpoint_exige_token():
    response = client.post('/v1/hub-lowcode/teams/graph/chats', json={'usuario_access_token': ''})
    assert response.status_code == 422
