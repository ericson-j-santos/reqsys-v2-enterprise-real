"""Testes da Opcao B (Power Platform Solutions) de provisionamento do flow_bot."""

import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import teams_flow_bot_provisioning as prov


def _run(coro):
    return asyncio.run(coro)


def _mock_response(json_body=None, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.raise_for_status = MagicMock()
    return resp


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_exportar_solution_faz_post_com_solution_name(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_response({'ExportSolutionFile': 'YmFzZTY0'})

        resultado = _run(prov.exportar_solution('https://org.crm2.dynamics.com', 'ReqSysTeamsGateway'))

    assert resultado == 'YmFzZTY0'
    args, kwargs = mock_post.await_args
    assert 'ExportSolution' in args[0]
    assert kwargs['json'] == {'SolutionName': 'ReqSysTeamsGateway', 'Managed': False}


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_importar_solution_valida_base64_antes_de_chamar_api(mock_token):
    mock_token.return_value = 'token-abc'

    with pytest.raises(Exception):
        _run(prov.importar_solution('https://org.crm2.dynamics.com', 'nao-e-base64-valido!!!'))

    mock_token.assert_not_awaited()


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_importar_solution_faz_post_com_customization_file(mock_token):
    mock_token.return_value = 'token-abc'
    zip_b64 = base64.b64encode(b'conteudo-zip-fake').decode()
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_response(status_code=200)

        resultado = _run(prov.importar_solution('https://org.crm2.dynamics.com', zip_b64))

    assert resultado['status_code'] == 200
    assert 'import_job_id' in resultado
    args, kwargs = mock_post.await_args
    assert 'ImportSolution' in args[0]
    assert kwargs['json']['CustomizationFile'] == zip_b64


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_obter_connection_reference_id_encontrado(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response({'value': [{'connectionreferenceid': 'guid-123'}]})

        resultado = _run(prov.obter_connection_reference_id('https://org.crm2.dynamics.com', 'reqsys_teams_ref'))

    assert resultado == 'guid-123'


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_obter_connection_reference_id_nao_encontrado_levanta_erro(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response({'value': []})

        with pytest.raises(ValueError, match='connectionreference nao encontrada'):
            _run(prov.obter_connection_reference_id('https://org.crm2.dynamics.com', 'ref_inexistente'))


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
@patch('app.services.teams_flow_bot_provisioning.obter_connection_reference_id', new_callable=AsyncMock)
def test_vincular_connection_reference_faz_patch_com_connection_id(mock_obter_id, mock_token):
    mock_obter_id.return_value = 'guid-123'
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.patch', new_callable=AsyncMock) as mock_patch:
        mock_patch.return_value = _mock_response(status_code=204)

        _run(prov.vincular_connection_reference('https://org.crm2.dynamics.com', 'reqsys_teams_ref', 'conn-novo-dono'))

    args, kwargs = mock_patch.await_args
    assert 'connectionreferences(guid-123)' in args[0]
    assert kwargs['json'] == {'connectionid': 'conn-novo-dono'}


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_obter_workflow_id_por_nome_encontrado(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response({'value': [{'workflowid': 'wf-guid-1'}]})

        resultado = _run(prov.obter_workflow_id_por_nome('https://org.crm2.dynamics.com', 'ReqSys Flow Backup 1'))

    assert resultado == 'wf-guid-1'


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_ativar_flow_faz_patch_statecode_activated(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.patch', new_callable=AsyncMock) as mock_patch:
        mock_patch.return_value = _mock_response(status_code=204)

        _run(prov.ativar_flow('https://org.crm2.dynamics.com', 'wf-guid-1'))

    args, kwargs = mock_patch.await_args
    assert 'workflows(wf-guid-1)' in args[0]
    assert kwargs['json'] == {'statecode': 1, 'statuscode': 2}


@patch('app.services.teams_flow_bot_provisioning.ativar_flow', new_callable=AsyncMock)
@patch('app.services.teams_flow_bot_provisioning.obter_workflow_id_por_nome', new_callable=AsyncMock)
@patch('app.services.teams_flow_bot_provisioning.vincular_connection_reference', new_callable=AsyncMock)
@patch('app.services.teams_flow_bot_provisioning.importar_solution', new_callable=AsyncMock)
@patch('app.services.teams_flow_bot_provisioning.exportar_solution', new_callable=AsyncMock)
def test_promover_flow_para_ambiente_fluxo_completo(
    mock_exportar, mock_importar, mock_vincular, mock_workflow_id, mock_ativar
):
    mock_exportar.return_value = 'zip-base64-fake'
    mock_importar.return_value = {'import_job_id': 'job-1', 'status_code': 200}
    mock_workflow_id.return_value = 'wf-guid-1'

    resultado = _run(
        prov.promover_flow_para_ambiente(
            environment_url_origem='https://org-dev.crm2.dynamics.com',
            environment_url_destino='https://org-prod.crm2.dynamics.com',
            solution_name='ReqSysTeamsGateway',
            connection_reference_logical_name='reqsys_teams_ref',
            connection_id_destino='conn-prod-dono',
            novo_flow_display_name='ReqSys Flow Bot - Prod',
        )
    )

    assert resultado['workflow_id'] == 'wf-guid-1'
    assert resultado['ativado'] is True
    assert resultado['connection_vinculada'] is True
    mock_exportar.assert_awaited_once_with('https://org-dev.crm2.dynamics.com', 'ReqSysTeamsGateway', managed=False)
    mock_importar.assert_awaited_once_with('https://org-prod.crm2.dynamics.com', 'zip-base64-fake')
    mock_vincular.assert_awaited_once_with(
        'https://org-prod.crm2.dynamics.com', 'reqsys_teams_ref', 'conn-prod-dono'
    )
    mock_ativar.assert_awaited_once_with('https://org-prod.crm2.dynamics.com', 'wf-guid-1')


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_exportar_solution_propaga_erro_http(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        request = httpx.Request('POST', 'https://org.crm2.dynamics.com/api/data/v9.2/ExportSolution')
        response = httpx.Response(404, request=request, text='solution nao encontrada')
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError('404', request=request, response=response)
        mock_post.return_value = resp

        with pytest.raises(httpx.HTTPStatusError):
            _run(prov.exportar_solution('https://org.crm2.dynamics.com', 'SolucaoInexistente'))


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_buscar_flows_por_nome_retorna_lista_ordenada(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(
            {
                'value': [
                    {'workflowid': 'wf-2', 'name': 'robo_envia_teams20260108v2', 'statecode': 1},
                    {'workflowid': 'wf-1', 'name': 'robo_envia_teams_v2.0.0', 'statecode': 0},
                ]
            }
        )

        resultado = _run(prov.buscar_flows_por_nome('https://org.crm2.dynamics.com', 'robo_envia_teams'))

    assert len(resultado) == 2
    assert resultado[0]['name'] == 'robo_envia_teams20260108v2'
    args, kwargs = mock_get.await_args
    assert "contains(name, 'robo_envia_teams')" in kwargs['params']['$filter']
    assert 'category eq 5' in kwargs['params']['$filter']


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_obter_solution_id_encontrada(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response({'value': [{'solutionid': 'sol-guid-1'}]})

        resultado = _run(prov.obter_solution_id('https://org.crm2.dynamics.com', 'robo_envia_mensagem_teams'))

    assert resultado == 'sol-guid-1'


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
def test_obter_solution_id_nao_encontrada_levanta_erro(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response({'value': []})

        with pytest.raises(ValueError, match='solution nao encontrada'):
            _run(prov.obter_solution_id('https://org.crm2.dynamics.com', 'solucao_inexistente'))


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
@patch('app.services.teams_flow_bot_provisioning.obter_solution_id', new_callable=AsyncMock)
def test_listar_workflows_da_solution_resolve_componentes(mock_obter_solution_id, mock_token):
    mock_obter_solution_id.return_value = 'sol-guid-1'
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            _mock_response({'value': [{'objectid': 'wf-guid-1'}]}),
            _mock_response({'value': [{'workflowid': 'wf-guid-1', 'name': 'robo_envia_teams20260108v2', 'statecode': 1}]}),
        ]

        resultado = _run(
            prov.listar_workflows_da_solution('https://org.crm2.dynamics.com', 'robo_envia_mensagem_teams')
        )

    assert len(resultado) == 1
    assert resultado[0]['name'] == 'robo_envia_teams20260108v2'
    assert mock_get.await_count == 2
    primeira_chamada_filtro = mock_get.await_args_list[0].kwargs['params']['$filter']
    assert 'componenttype eq 29' in primeira_chamada_filtro
    assert 'sol-guid-1' in primeira_chamada_filtro


@patch('app.services.teams_flow_bot_provisioning._token_dataverse', new_callable=AsyncMock)
@patch('app.services.teams_flow_bot_provisioning.obter_solution_id', new_callable=AsyncMock)
def test_listar_workflows_da_solution_sem_componentes_retorna_lista_vazia(mock_obter_solution_id, mock_token):
    mock_obter_solution_id.return_value = 'sol-guid-1'
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response({'value': []})

        resultado = _run(
            prov.listar_workflows_da_solution('https://org.crm2.dynamics.com', 'solucao_vazia')
        )

    assert resultado == []
    mock_get.assert_awaited_once()
