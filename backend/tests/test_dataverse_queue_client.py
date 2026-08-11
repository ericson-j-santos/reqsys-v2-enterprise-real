"""Testes do adapter Dataverse genérico (app/services/dataverse_queue_client.py)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import dataverse_queue_client as module
from app.services.dataverse_queue_client import DataverseError

ENV = 'https://org.crm2.dynamics.com'


def _run(coro):
    return asyncio.run(coro)


def _mock_response(json_body=None, status_code=200, text=''):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.text = text
    return resp


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    # Os testes de transporte mockam a aquisição do token, mas `_request`
    # mantém o fail-fast de configuração para produção. Isole o ambiente do
    # runner com credenciais sintéticas para que cada teste alcance o ponto
    # explicitamente mockado.
    monkeypatch.setattr(module.settings, 'azure_tenant_id', 'tenant-test')
    monkeypatch.setattr(module.settings, 'azure_client_id', 'client-test')
    monkeypatch.setattr(module.settings, 'azure_client_secret', 'secret-test')
    module.reset_circuit_breakers()
    yield
    module.reset_circuit_breakers()


@patch('app.services.dataverse_queue_client.settings')
def test_dataverse_configurado_reflete_settings(mock_settings):
    mock_settings.azure_tenant_id = ''
    mock_settings.azure_client_id = 'x'
    mock_settings.azure_client_secret = 'y'
    assert module.dataverse_configurado() is False

    mock_settings.azure_tenant_id = 't'
    assert module.dataverse_configurado() is True


@patch('app.services.dataverse_queue_client.settings')
def test_request_levanta_erro_quando_nao_configurado(mock_settings):
    mock_settings.azure_tenant_id = ''
    mock_settings.azure_client_id = ''
    mock_settings.azure_client_secret = ''

    with pytest.raises(DataverseError, match='não configurado'):
        _run(module._request(ENV, 'GET', 'cr85a_redminequeues'))


@patch('app.services.dataverse_queue_client._token', new_callable=AsyncMock)
def test_request_propaga_erro_http_4xx_sem_retry(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = _mock_response(status_code=400, text='String or binary data would be truncated')

        with pytest.raises(DataverseError, match='HTTP 400'):
            _run(module._request(ENV, 'PATCH', "cr85a_agilesyncs(row-1)", json_payload={'cr85a_correlationid': 'x'}))

    mock_request.assert_awaited_once()


@patch('app.services.dataverse_queue_client._token', new_callable=AsyncMock)
def test_resolver_entity_set_name_usa_cache(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = _mock_response({'EntitySetName': 'cr85a_redminequeues'})

        primeiro = _run(module.resolver_entity_set_name(ENV, 'cr85a_redminequeue'))
        segundo = _run(module.resolver_entity_set_name(ENV, 'cr85a_redminequeue'))

    assert primeiro == segundo == 'cr85a_redminequeues'
    mock_request.assert_awaited_once()  # segunda chamada veio do cache, sem nova requisição


@patch('app.services.dataverse_queue_client._token', new_callable=AsyncMock)
def test_list_rows_monta_query_string(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = _mock_response({'value': [{'cr85a_redminequeueid': '1'}]})

        resultado = _run(module.list_rows(
            ENV, 'cr85a_redminequeues', filtro="cr85a_status eq 'PENDING'", select=['cr85a_redminequeueid'], top=10,
        ))

    assert resultado == [{'cr85a_redminequeueid': '1'}]
    args, kwargs = mock_request.await_args
    assert '$filter=' in args[1]
    assert '$select=cr85a_redminequeueid' in args[1]
    assert '$top=10' in args[1]


@patch('app.services.dataverse_queue_client._token', new_callable=AsyncMock)
def test_metadados_coluna_busca_maxlength_para_string(mock_token):
    mock_token.return_value = 'token-abc'
    respostas = [
        _mock_response({'AttributeType': 'String', 'LogicalName': 'cr85a_correlationid'}),
        _mock_response({'MaxLength': 20}),
    ]
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock, side_effect=respostas):
        resultado = _run(module.metadados_coluna(ENV, 'cr85a_agilesync', 'cr85a_correlationid'))

    assert resultado == {'logical_name': 'cr85a_correlationid', 'attribute_type': 'String', 'max_length': 20}


@patch('app.services.dataverse_queue_client._token', new_callable=AsyncMock)
def test_verificar_application_user_encontrado(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = _mock_response({'value': [{'systemuserid': 'su-1', 'fullname': 'ReqSys App'}]})

        resultado = _run(module.verificar_application_user(ENV, 'client-id-1'))

    assert resultado == {'existe': True, 'systemuserid': 'su-1'}


@patch('app.services.dataverse_queue_client._token', new_callable=AsyncMock)
def test_verificar_application_user_ausente(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = _mock_response({'value': []})

        resultado = _run(module.verificar_application_user(ENV, 'client-id-1'))

    assert resultado == {'existe': False, 'systemuserid': None}


@patch('app.services.dataverse_queue_client._token', new_callable=AsyncMock)
def test_listar_colunas_retorna_lista_de_atributos(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = _mock_response({'value': [
            {'LogicalName': 'cr85a_correlationid', 'AttributeType': 'String'},
            {'LogicalName': 'cr85a_trackerid', 'AttributeType': 'Integer'},
        ]})

        resultado = _run(module.listar_colunas(ENV, 'cr85a_redminequeue'))

    assert resultado[0]['LogicalName'] == 'cr85a_correlationid'
    assert resultado[1]['AttributeType'] == 'Integer'


@patch('app.services.dataverse_queue_client._token', new_callable=AsyncMock)
def test_testar_autenticacao_devolve_token(mock_token):
    mock_token.return_value = 'token-xyz'

    resultado = _run(module.testar_autenticacao(ENV))

    assert resultado == 'token-xyz'
    mock_token.assert_awaited_once_with(ENV)


@patch('app.services.dataverse_queue_client._token', new_callable=AsyncMock)
def test_request_propaga_falha_de_rede_como_dataverse_error(mock_token):
    mock_token.return_value = 'token-abc'
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock, side_effect=httpx.ConnectError('offline')):
        with pytest.raises(DataverseError, match='Falha de rede'):
            _run(module._request(ENV, 'GET', 'cr85a_redminequeues'))
