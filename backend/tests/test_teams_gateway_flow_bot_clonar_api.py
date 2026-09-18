"""Testes da API de clonagem de flow do canal flow_bot."""

from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.core.security import require_admin
from app.main import app

client = TestClient(app)


def _fake_admin():
    return {'papel': 'admin'}


@patch('app.api.teams_gateway.clonar_flow_para_novo_dono', new_callable=AsyncMock)
def test_clonar_flow_sucesso(mock_clonar):
    mock_clonar.return_value = {'name': 'flow-clonado'}
    app.dependency_overrides[require_admin] = _fake_admin
    try:
        response = client.post(
            '/v1/teams-gateway/flow-bot/clonar-flow',
            json={
                'environment': 'env-1',
                'flow_id_origem': 'flow-origem',
                'nova_connection_id': 'conn-backup',
                'novo_display_name': 'Backup 1',
            },
        )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    assert response.json()['data'] == {'name': 'flow-clonado'}
    mock_clonar.assert_awaited_once()


@patch('app.api.teams_gateway.clonar_flow_para_novo_dono', new_callable=AsyncMock)
def test_clonar_flow_erro_http_vira_502(mock_clonar):
    request = httpx.Request('PUT', 'https://api.flow.microsoft.com/x')
    response_obj = httpx.Response(403, request=request, text='forbidden')
    mock_clonar.side_effect = httpx.HTTPStatusError('403', request=request, response=response_obj)
    app.dependency_overrides[require_admin] = _fake_admin
    try:
        response = client.post(
            '/v1/teams-gateway/flow-bot/clonar-flow',
            json={
                'environment': 'env-1',
                'flow_id_origem': 'flow-origem',
                'nova_connection_id': 'conn-backup',
                'novo_display_name': 'Backup 1',
            },
        )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 502


def test_clonar_flow_sem_admin_retorna_401_ou_403():
    response = client.post(
        '/v1/teams-gateway/flow-bot/clonar-flow',
        json={
            'environment': 'env-1',
            'flow_id_origem': 'flow-origem',
            'nova_connection_id': 'conn-backup',
            'novo_display_name': 'Backup 1',
        },
    )

    assert response.status_code in (401, 403)
