"""Testes da API de promocao do flow_bot entre ambientes via Solution."""

from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.core.security import require_admin
from app.main import app

client = TestClient(app)


def _fake_admin():
    return {'papel': 'admin'}


_PAYLOAD = {
    'environment_url_origem': 'https://org-dev.crm2.dynamics.com',
    'environment_url_destino': 'https://org-prod.crm2.dynamics.com',
    'solution_name': 'ReqSysTeamsGateway',
    'connection_reference_logical_name': 'reqsys_teams_ref',
    'connection_id_destino': 'conn-prod-dono',
    'novo_flow_display_name': 'ReqSys Flow Bot - Prod',
}


@patch('app.api.teams_gateway.promover_flow_para_ambiente', new_callable=AsyncMock)
def test_promover_solution_sucesso(mock_promover):
    mock_promover.return_value = {'workflow_id': 'wf-1', 'ativado': True, 'connection_vinculada': True}
    app.dependency_overrides[require_admin] = _fake_admin
    try:
        response = client.post('/v1/teams-gateway/flow-bot/promover-solution', json=_PAYLOAD)
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    assert response.json()['data']['workflow_id'] == 'wf-1'
    mock_promover.assert_awaited_once()


@patch('app.api.teams_gateway.promover_flow_para_ambiente', new_callable=AsyncMock)
def test_promover_solution_erro_http_vira_502(mock_promover):
    request = httpx.Request('POST', 'https://org.crm2.dynamics.com/x')
    response_obj = httpx.Response(403, request=request, text='forbidden')
    mock_promover.side_effect = httpx.HTTPStatusError('403', request=request, response=response_obj)
    app.dependency_overrides[require_admin] = _fake_admin
    try:
        response = client.post('/v1/teams-gateway/flow-bot/promover-solution', json=_PAYLOAD)
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 502


def test_promover_solution_sem_admin_retorna_401_ou_403():
    response = client.post('/v1/teams-gateway/flow-bot/promover-solution', json=_PAYLOAD)

    assert response.status_code in (401, 403)
