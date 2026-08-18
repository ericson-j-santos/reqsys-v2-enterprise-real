"""Caminhos criticos da API Teams Messaging Gateway."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_teams_gateway_status_endpoint():
    response = client.get('/v1/teams-gateway/status')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['schema_version'] == '1.1.0'
    assert {rota['canal'] for rota in data['rotas']} >= {'graph_delegado', 'webhook', 'graph_app_only', 'bot'}


@patch('app.api.teams_gateway.teams_graph_identity_status')
def test_teams_gateway_status_graph_app_only_usa_registro_governado(mock_status_identidade):
    mock_status_identidade.return_value = {
        'configured': True,
        'profile_name': 'reqsys-dev-teams-confidential',
        'environment': 'development',
        'client_id_suffix': '12345678',
        'rotation_due_at': '2026-09-01T12:00:00+00:00',
        'rotation_required': False,
    }

    response = client.get('/v1/teams-gateway/status')

    assert response.status_code == 200
    rotas = response.json()['data']['rotas']
    graph_app = next(rota for rota in rotas if rota['canal'] == 'graph_app_only')
    assert graph_app['disponivel'] is True
    assert graph_app['campos_faltantes'] == []
    mock_status_identidade.assert_called_once_with()


def test_teams_gateway_identity_status_exige_admin():
    response = client.get('/v1/teams-gateway/identity-status')

    assert response.status_code in (401, 403)


def test_teams_gateway_routes_endpoint():
    response = client.post(
        '/v1/teams-gateway/routes',
        json={
            'destino_tipo': 'chat',
            'destino_id': 'chat-1',
            'texto': 'Ola',
            'usuario_access_token': 'token',
        },
    )

    assert response.status_code == 200
    assert response.json()['data']['canal'] == 'graph_delegado'


@patch('app.api.teams_gateway.enviar_mensagem_gateway', new_callable=AsyncMock)
def test_teams_gateway_messages_endpoint(mock_enviar):
    mock_enviar.return_value = {
        'entregue': True,
        'canal_usado': 'graph_delegado',
        'destino_tipo': 'chat',
        'correlation_id': 'corr-api',
        'dry_run': False,
        'fallback_usado': False,
        'message_id': 'msg-1',
        'chat_id': 'chat-1',
        'status_code': None,
        'erro': None,
        'motivo': None,
        'provider_response': {},
    }

    response = client.post(
        '/v1/teams-gateway/messages',
        headers={'X-Correlation-ID': 'corr-api'},
        json={
            'destino_tipo': 'chat',
            'destino_id': 'chat-1',
            'texto': 'Ola',
            'usuario_access_token': 'token',
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body['data']['entregue'] is True
    assert body['meta']['correlation_id'] == 'corr-api'
    mock_enviar.assert_awaited_once()


def test_teams_gateway_messages_valida_payload():
    response = client.post('/v1/teams-gateway/messages', json={'texto': ''})

    assert response.status_code == 422


@patch('app.api.teams_gateway.enviar_mensagem_gateway', new_callable=AsyncMock)
def test_teams_gateway_webhook_shortcut_forca_modo_webhook(mock_enviar):
    async def _fake(payload, db=None, correlation_id=None):
        assert payload.modo == 'webhook'
        return {
            'entregue': True,
            'canal_usado': 'webhook',
            'destino_tipo': payload.destino_tipo,
            'correlation_id': correlation_id or 'corr',
            'dry_run': False,
            'fallback_usado': False,
            'message_id': None,
            'chat_id': None,
            'status_code': 200,
            'erro': None,
            'motivo': None,
            'provider_response': {},
        }

    mock_enviar.side_effect = _fake

    response = client.post(
        '/v1/teams-gateway/messages/webhook',
        json={
            'destino_tipo': 'canal',
            'texto': 'Alerta',
            'webhook_url': 'https://example.invalid/webhook',
        },
    )

    assert response.status_code == 200
    assert response.json()['data']['canal_usado'] == 'webhook'
