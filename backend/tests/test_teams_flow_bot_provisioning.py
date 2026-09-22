"""Testes do modulo de clonagem de flow (Flow Management API) para novos donos do flow_bot."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import teams_flow_bot_provisioning as prov


def _run(coro):
    return asyncio.run(coro)


_DEFINICAO_ORIGEM = {
    'id': '/providers/Microsoft.ProcessSimple/environments/env-1/flows/flow-origem',
    'name': 'flow-origem',
    'properties': {
        'displayName': 'ReqSys Teams Gateway Webhook (Ericson)',
        'createdTime': '2026-07-01T00:00:00Z',
        'lastModifiedTime': '2026-07-01T00:00:00Z',
        'definition': {
            'triggers': {'manual': {'type': 'Request', 'kind': 'Http'}},
            'actions': {'Post_message_in_a_chat_or_channel': {'type': 'OpenApiConnection'}},
        },
        'connectionReferences': {
            'shared_teams': {
                'connection': {'id': '/providers/.../connections/conn-ericson'},
                'api': {'name': 'shared_teams'},
            }
        },
    },
}


@patch('app.services.teams_flow_bot_provisioning.token_power_automate', new_callable=AsyncMock)
def test_capturar_definicao_flow_faz_get_autenticado(mock_token):
    mock_token.return_value = 'token-abc'

    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = _DEFINICAO_ORIGEM
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        resultado = _run(prov.capturar_definicao_flow('env-1', 'flow-origem'))

    assert resultado == _DEFINICAO_ORIGEM
    mock_get.assert_awaited_once()
    args, kwargs = mock_get.await_args
    assert 'env-1' in args[0]
    assert 'flow-origem' in args[0]
    assert kwargs['headers']['Authorization'] == 'Bearer token-abc'


def test_clonar_definicao_para_novo_dono_troca_connection_id_e_remove_campos_readonly():
    clone = prov.clonar_definicao_para_novo_dono(
        _DEFINICAO_ORIGEM,
        nova_connection_id='/providers/.../connections/conn-backup',
        novo_display_name='ReqSys Teams Gateway Webhook (Backup 1)',
    )

    assert clone['properties']['displayName'] == 'ReqSys Teams Gateway Webhook (Backup 1)'
    assert clone['properties']['connectionReferences']['shared_teams']['connection']['id'] == (
        '/providers/.../connections/conn-backup'
    )
    assert 'id' not in clone
    assert 'name' not in clone
    assert 'createdTime' not in clone['properties']
    assert clone['properties']['state'] == 'Started'
    # nao deve mutar o dicionario original
    assert _DEFINICAO_ORIGEM['properties']['connectionReferences']['shared_teams']['connection']['id'] == (
        '/providers/.../connections/conn-ericson'
    )


def test_clonar_definicao_sem_connection_references_levanta_erro():
    definicao_invalida = {'properties': {'displayName': 'X'}}

    with pytest.raises(ValueError, match='connectionReferences'):
        prov.clonar_definicao_para_novo_dono(definicao_invalida, 'conn-x', 'Novo')


def test_clonar_definicao_com_chave_inexistente_levanta_erro():
    with pytest.raises(ValueError, match='connection_reference_key'):
        prov.clonar_definicao_para_novo_dono(
            _DEFINICAO_ORIGEM, 'conn-x', 'Novo', connection_reference_key='chave_que_nao_existe'
        )


@patch('app.services.teams_flow_bot_provisioning.token_power_automate', new_callable=AsyncMock)
def test_criar_flow_a_partir_definicao_faz_put_autenticado(mock_token):
    mock_token.return_value = 'token-abc'

    with patch('httpx.AsyncClient.put', new_callable=AsyncMock) as mock_put:
        mock_response = MagicMock()
        mock_response.json.return_value = {'name': 'novo-flow-id'}
        mock_response.raise_for_status = MagicMock()
        mock_put.return_value = mock_response

        resultado = _run(prov.criar_flow_a_partir_definicao('env-1', 'novo-flow-id', {'properties': {}}))

    assert resultado == {'name': 'novo-flow-id'}
    mock_put.assert_awaited_once()


@patch('app.services.teams_flow_bot_provisioning.criar_flow_a_partir_definicao', new_callable=AsyncMock)
@patch('app.services.teams_flow_bot_provisioning.capturar_definicao_flow', new_callable=AsyncMock)
def test_clonar_flow_para_novo_dono_fluxo_completo(mock_capturar, mock_criar):
    mock_capturar.return_value = _DEFINICAO_ORIGEM
    mock_criar.return_value = {'name': 'flow-clonado'}

    resultado = _run(
        prov.clonar_flow_para_novo_dono(
            environment='env-1',
            flow_id_origem='flow-origem',
            nova_connection_id='conn-backup',
            novo_display_name='Backup 1',
            novo_flow_id='flow-clonado',
        )
    )

    assert resultado == {'name': 'flow-clonado'}
    mock_capturar.assert_awaited_once_with('env-1', 'flow-origem')
    mock_criar.assert_awaited_once()
    env_arg, flow_id_arg, definicao_arg = mock_criar.await_args.args
    assert env_arg == 'env-1'
    assert flow_id_arg == 'flow-clonado'
    assert definicao_arg['properties']['displayName'] == 'Backup 1'


@patch('app.services.teams_flow_bot_provisioning.token_power_automate', new_callable=AsyncMock)
def test_capturar_definicao_flow_propaga_erro_http(mock_token):
    mock_token.return_value = 'token-abc'

    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        request = httpx.Request('GET', 'https://api.flow.microsoft.com/x')
        response = httpx.Response(404, request=request, text='nao encontrado')
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError('404', request=request, response=response)
        mock_get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            _run(prov.capturar_definicao_flow('env-1', 'flow-inexistente'))
