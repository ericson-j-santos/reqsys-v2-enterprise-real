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


def test_lowcode_solution_generate_endpoint():
    response = client.post(
        '/v1/hub-lowcode/solutions/generate',
        json={
            'solution_name': 'ReqSysLowCode',
            'display_name': 'ReqSys Low-Code',
            'target_environment': 'dev',
            'dry_run': True,
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['capability'] == 'LowCode Solution Factory P0'
    assert data['apps']['canvas_app']['app_type'] == 'canvas'
    assert data['dataverse']['tables']
    assert data['package']['zip_base64']


def test_lowcode_solution_generate_canvas_endpoint():
    response = client.post(
        '/v1/hub-lowcode/solutions/generate/canvas',
        json={'solution_name': 'ReqSysLowCode', 'display_name': 'ReqSys Low-Code'},
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['solution_name'] == 'ReqSysLowCode'
    assert 'Canvas App' in data['canvas_markdown']
    assert data['canvas_app']['start_screen'] == 'scrDashboard'


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


@patch('app.api.hub_lowcode.registrar_manifesto_provisionamento')
@patch('app.api.hub_lowcode.gerar_manifesto_provisionamento_flow')
def test_power_automate_flow_provisioning_plan_endpoint(mock_gerar, mock_registrar):
    mock_gerar.return_value = {'correlation_id': 'corr-plan-1', 'display_name': 'Flow Teste'}
    mock_registrar.return_value = None

    response = client.post(
        '/v1/hub-lowcode/power-automate/flows/provisioning-plan',
        json={'display_name': 'Flow Teste Provisionamento', 'dry_run': True, 'registrar': False},
        headers={'X-Correlation-Id': 'corr-plan-1'},
    )

    assert response.status_code == 200
    assert response.json()['data']['manifesto']['correlation_id'] == 'corr-plan-1'


@patch('app.api.hub_lowcode.salvar_log_integracao')
@patch('app.api.hub_lowcode.serializar_registry')
@patch('app.api.hub_lowcode.registrar_manifesto_provisionamento')
@patch('app.api.hub_lowcode.despachar_workflow_provisionamento', new_callable=AsyncMock)
@patch('app.api.hub_lowcode.gerar_manifesto_provisionamento_flow')
def test_power_automate_flow_provision_dispatched(mock_gerar, mock_dispatch, mock_registrar, mock_serializar, mock_log):
    mock_gerar.return_value = {'correlation_id': 'corr-prov-1', 'display_name': 'Flow Dispatch'}
    mock_dispatch.return_value = {'dispatched': True, 'workflow': 'alm'}
    registry = type('Registry', (), {'id': 42})()
    mock_registrar.return_value = registry
    mock_serializar.return_value = {'id': 42, 'correlation_id': 'corr-prov-1', 'status': 'dispatched'}

    response = client.post(
        '/v1/hub-lowcode/power-automate/flows/provision',
        json={'display_name': 'Flow Dispatch Provisionamento'},
        headers={'X-Correlation-Id': 'corr-prov-1'},
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['dispatch']['dispatched'] is True
    mock_log.assert_called_once()


@patch('app.api.hub_lowcode.salvar_log_integracao')
@patch('app.api.hub_lowcode.serializar_registry')
@patch('app.api.hub_lowcode.registrar_manifesto_provisionamento')
@patch('app.api.hub_lowcode.despachar_workflow_provisionamento', new_callable=AsyncMock)
@patch('app.api.hub_lowcode.gerar_manifesto_provisionamento_flow')
def test_power_automate_flow_provision_pending_configuration(mock_gerar, mock_dispatch, mock_registrar, mock_serializar, mock_log):
    mock_gerar.return_value = {'correlation_id': 'corr-pend-1', 'display_name': 'Flow Pendente'}
    mock_dispatch.return_value = {'dispatched': False, 'motivo': 'GITHUB_PAT ausente'}
    registry = type('Registry', (), {'id': 7})()
    mock_registrar.return_value = registry
    mock_serializar.return_value = {'id': 7, 'correlation_id': 'corr-pend-1', 'status': 'pending_configuration'}

    response = client.post(
        '/v1/hub-lowcode/power-automate/flows/provision',
        json={'display_name': 'Flow Pendente Provisionamento'},
    )

    assert response.status_code == 200
    assert response.json()['data']['dispatch']['dispatched'] is False
    mock_log.assert_called_once()


@patch('app.api.hub_lowcode.listar_registry_provisionamentos')
def test_power_automate_provisioning_registry_endpoint(mock_listar):
    mock_listar.return_value = [{'correlation_id': 'corr-1'}]
    response = client.get('/v1/hub-lowcode/power-automate/flows/provisioning-registry?status=planned')
    assert response.status_code == 200
    assert response.json()['data']['items'][0]['correlation_id'] == 'corr-1'


@patch('app.api.hub_lowcode.resumo_registry_provisionamentos')
def test_power_automate_provisioning_registry_summary_endpoint(mock_resumo):
    mock_resumo.return_value = {'total': 2, 'por_status': {'planned': 1}}
    response = client.get('/v1/hub-lowcode/power-automate/flows/provisioning-registry/summary')
    assert response.status_code == 200
    assert response.json()['data']['total'] == 2


@patch('app.api.hub_lowcode.testar_teams_webhook', new_callable=AsyncMock)
@patch('app.api.hub_lowcode.obter_planner_webhook_config')
def test_teams_testar_webhook_usa_config_quando_url_ausente(mock_cfg, mock_testar):
    mock_cfg.return_value = {'teams_webhook_url': 'https://teams.example/webhook'}
    mock_testar.return_value = {'ok': True}

    response = client.post('/v1/hub-lowcode/teams/testar-webhook')

    assert response.status_code == 200
    mock_testar.assert_awaited_once_with('https://teams.example/webhook')


@patch('app.api.hub_lowcode.testar_teams_webhook', new_callable=AsyncMock)
def test_teams_testar_webhook_com_url_explicita(mock_testar):
    mock_testar.return_value = {'ok': True}
    response = client.post(
        '/v1/hub-lowcode/teams/testar-webhook',
        json='https://teams.example/custom',
    )
    assert response.status_code == 200
    mock_testar.assert_awaited_once_with('https://teams.example/custom')
