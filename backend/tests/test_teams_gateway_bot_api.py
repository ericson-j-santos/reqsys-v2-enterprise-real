"""Caminhos criticos da API do canal 'bot' do Teams Messaging Gateway."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_teams_gateway_bot_messages_sem_token_retorna_401():
    response = client.post('/v1/teams-gateway/bot/messages', json={'type': 'message'})

    assert response.status_code == 401


@patch('app.api.teams_gateway.validar_jwt_bot_framework')
def test_teams_gateway_bot_messages_token_invalido_retorna_401(mock_validar):
    mock_validar.side_effect = ValueError('assinatura invalida')

    response = client.post(
        '/v1/teams-gateway/bot/messages',
        headers={'Authorization': 'Bearer token-invalido'},
        json={'type': 'message'},
    )

    assert response.status_code == 401


@patch('app.api.teams_gateway.salvar_conversa_referencia_bot')
@patch('app.api.teams_gateway.validar_jwt_bot_framework')
def test_teams_gateway_bot_messages_conversation_update_persiste_referencia(mock_validar, mock_salvar):
    mock_validar.return_value = {'aud': 'bot-app-id', 'iss': 'https://api.botframework.com'}
    mock_salvar.return_value = MagicMock()

    activity = {
        'type': 'conversationUpdate',
        'serviceUrl': 'https://smba.trafficmanager.net/br/',
        'from': {'id': '29:abc', 'aadObjectId': 'aad-usuario-1'},
        'recipient': {'id': '28:bot-id'},
        'conversation': {'id': 'a:conv-1'},
        'channelData': {'tenant': {'id': 'tenant-1'}},
        'membersAdded': [{'id': '28:bot-id'}],
    }

    response = client.post(
        '/v1/teams-gateway/bot/messages',
        headers={'Authorization': 'Bearer token-valido'},
        json=activity,
    )

    assert response.status_code == 200
    assert response.json()['data']['recebido'] is True
    mock_salvar.assert_called_once()
    _, kwargs = mock_salvar.call_args
    assert kwargs['usuario_aad_object_id'] == 'aad-usuario-1'
    assert kwargs['conversation_id'] == 'a:conv-1'
    assert kwargs['service_url'] == 'https://smba.trafficmanager.net/br/'
    assert kwargs['tenant_id'] == 'tenant-1'


@patch('app.api.teams_gateway.salvar_conversa_referencia_bot')
@patch('app.api.teams_gateway.validar_jwt_bot_framework')
def test_teams_gateway_bot_messages_sem_aad_object_id_nao_persiste(mock_validar, mock_salvar):
    mock_validar.return_value = {'aud': 'bot-app-id'}

    activity = {
        'type': 'message',
        'serviceUrl': 'https://smba.trafficmanager.net/br/',
        'from': {'id': '29:abc'},
        'conversation': {'id': 'a:conv-1'},
    }

    response = client.post(
        '/v1/teams-gateway/bot/messages',
        headers={'Authorization': 'Bearer token-valido'},
        json=activity,
    )

    assert response.status_code == 200
    mock_salvar.assert_not_called()
