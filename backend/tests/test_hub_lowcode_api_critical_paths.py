"""Caminhos críticos — API hub low-code."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch('app.api.hub_lowcode.status_consolidado', new_callable=AsyncMock)
def test_hub_status_endpoint(mock_status):
    mock_status.return_value = {'pacotes_configurado': True, 'gerado_em': '2026-06-30T00:00:00Z'}
    response = client.get('/v1/hub-lowcode/status')
    assert response.status_code == 200
    assert response.json()['data']['pacotes_configurado'] is True


@patch('app.api.hub_lowcode.listar_pacotes_ia', new_callable=AsyncMock)
def test_hub_pacotes_endpoint(mock_listar):
    mock_listar.return_value = {'configurado': False, 'itens': [], 'erro': None}
    response = client.get('/v1/hub-lowcode/pacotes?limit=5')
    assert response.status_code == 200
    assert response.json()['data']['configurado'] is False


@patch('app.api.hub_lowcode.listar_flows_pa', new_callable=AsyncMock)
def test_hub_flows_endpoint(mock_listar):
    mock_listar.return_value = {'configurado': True, 'flows': [], 'erro': None}
    response = client.get('/v1/hub-lowcode/flows')
    assert response.status_code == 200
    assert response.json()['data']['configurado'] is True


@patch('app.api.hub_lowcode.listar_runs_github', new_callable=AsyncMock)
def test_hub_github_endpoint(mock_listar):
    mock_listar.return_value = {'configurado': True, 'runs': [], 'erro': None}
    response = client.get('/v1/hub-lowcode/github?limit=3')
    assert response.status_code == 200
    assert response.json()['data']['runs'] == []


@patch('app.api.hub_lowcode.listar_ambientes_powerplatform', new_callable=AsyncMock)
def test_hub_pp_ambientes_endpoint(mock_listar):
    mock_listar.return_value = {'configurado': True, 'ambientes': [{'nome': 'Dev'}], 'erro': None}
    response = client.get('/v1/hub-lowcode/powerplatform/ambientes')
    assert response.status_code == 200
    assert response.json()['data']['ambientes'][0]['nome'] == 'Dev'


@patch('app.api.hub_lowcode.obter_planner_webhook_config')
def test_hub_planner_webhook_config_endpoint(mock_obter):
    mock_obter.return_value = {
        'configurado': False,
        'teams_configurado': False,
        'planner_webhook_url': '',
        'webhook_url': '',
    }
    response = client.get('/v1/hub-lowcode/planner/webhook-config')
    assert response.status_code == 200
    assert response.json()['data']['configurado'] is False


@patch('app.api.hub_lowcode.listar_historico_integracoes')
def test_hub_historico_integracoes_endpoint(mock_listar):
    mock_listar.return_value = {'total': 0, 'eventos': []}
    response = client.get('/v1/hub-lowcode/integracoes/historico?tipo=planner&limit=5')
    assert response.status_code == 200
    assert response.json()['data']['total'] == 0
