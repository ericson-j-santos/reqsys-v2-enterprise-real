"""Testes da API de promocao do flow_bot entre ambientes via Solution."""

from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.api.teams_gateway import require_promover_solution_auth
from app.core.service_tokens import ServiceAuthContext
from app.main import app

client = TestClient(app)


def _fake_ctx():
    return ServiceAuthContext(ator='admin@teste', via_token=False)


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
    app.dependency_overrides[require_promover_solution_auth] = _fake_ctx
    try:
        response = client.post('/v1/teams-gateway/flow-bot/promover-solution', json=_PAYLOAD)
    finally:
        app.dependency_overrides.pop(require_promover_solution_auth, None)

    assert response.status_code == 200
    assert response.json()['data']['workflow_id'] == 'wf-1'
    mock_promover.assert_awaited_once()


@patch('app.api.teams_gateway.promover_flow_para_ambiente', new_callable=AsyncMock)
def test_promover_solution_erro_http_vira_502(mock_promover):
    request = httpx.Request('POST', 'https://org.crm2.dynamics.com/x')
    response_obj = httpx.Response(403, request=request, text='forbidden')
    mock_promover.side_effect = httpx.HTTPStatusError('403', request=request, response=response_obj)
    app.dependency_overrides[require_promover_solution_auth] = _fake_ctx
    try:
        response = client.post('/v1/teams-gateway/flow-bot/promover-solution', json=_PAYLOAD)
    finally:
        app.dependency_overrides.pop(require_promover_solution_auth, None)

    assert response.status_code == 502


def test_promover_solution_sem_credencial_retorna_401():
    response = client.post('/v1/teams-gateway/flow-bot/promover-solution', json=_PAYLOAD)

    assert response.status_code == 401


class TestPromoverSolutionViaServiceToken:
    """Cobre o caminho de automacao (X-Service-Token) alem do JWT admin humano."""

    def _criar_admin_token(self):
        resp = client.post('/v1/auth/login', json={'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com'})
        return resp.json()['data']['access_token']

    def _criar_service_token(self, scopes):
        headers = {'Authorization': f'Bearer {self._criar_admin_token()}'}
        resp = client.post('/v1/admin/service-tokens', json={'label': 'ci-teste', 'scopes': scopes}, headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()['data']['token']

    @patch('app.api.teams_gateway.promover_flow_para_ambiente', new_callable=AsyncMock)
    def test_token_com_escopo_correto_autentica(self, mock_promover):
        mock_promover.return_value = {'workflow_id': 'wf-2', 'ativado': True, 'connection_vinculada': True}
        token = self._criar_service_token(['teams_gateway:promover_solution'])

        response = client.post(
            '/v1/teams-gateway/flow-bot/promover-solution',
            json=_PAYLOAD,
            headers={'X-Service-Token': token},
        )

        assert response.status_code == 200
        assert response.json()['data']['workflow_id'] == 'wf-2'

    def test_token_com_escopo_errado_retorna_403(self):
        token = self._criar_service_token(['outro:escopo'])

        response = client.post(
            '/v1/teams-gateway/flow-bot/promover-solution',
            json=_PAYLOAD,
            headers={'X-Service-Token': token},
        )

        assert response.status_code == 403

    def test_token_revogado_retorna_401(self):
        headers_admin = {'Authorization': f'Bearer {self._criar_admin_token()}'}
        create_resp = client.post(
            '/v1/admin/service-tokens',
            json={'label': 'ci-revogar', 'scopes': ['teams_gateway:promover_solution']},
            headers=headers_admin,
        )
        token_id = create_resp.json()['data']['id']
        token = create_resp.json()['data']['token']
        revoke_resp = client.delete(f'/v1/admin/service-tokens/{token_id}', headers=headers_admin)
        assert revoke_resp.status_code == 200

        response = client.post(
            '/v1/teams-gateway/flow-bot/promover-solution',
            json=_PAYLOAD,
            headers={'X-Service-Token': token},
        )

        assert response.status_code == 401

    def test_token_invalido_retorna_401(self):
        response = client.post(
            '/v1/teams-gateway/flow-bot/promover-solution',
            json=_PAYLOAD,
            headers={'X-Service-Token': 'token-que-nao-existe'},
        )

        assert response.status_code == 401
