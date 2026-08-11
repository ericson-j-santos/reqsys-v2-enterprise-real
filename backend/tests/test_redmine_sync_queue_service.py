"""Testes do worker Redmine Sync Queue (fecha o loop de PA-001-CreateRedmineIssue)."""
import asyncio
from unittest.mock import AsyncMock, patch

from app.services import redmine_sync_queue as module
from app.services.github_redmine import IntegracaoError

ENV = 'https://org.crm2.dynamics.com'


def _run(coro):
    return asyncio.run(coro)


async def _resolver_entity_set(_env, logical_name):
    return f'{logical_name}s'


def test_mascarar_remove_api_key_e_bearer():
    bruto = "HTTP 401 em /issues.json: {'X-Redmine-API-Key': 'abc123segredo'} Bearer eyJhbGciOi.abc.def"
    resultado = module._mascarar(bruto)

    assert 'abc123segredo' not in resultado
    assert 'eyJhbGciOi' not in resultado
    assert '[SEGREDO_REMOVIDO]' in resultado


@patch('app.services.redmine_sync_queue.dv.resolver_entity_set_name', new=AsyncMock(side_effect=_resolver_entity_set))
@patch('app.services.redmine_sync_queue.dv.update_row', new_callable=AsyncMock)
@patch('app.services.redmine_sync_queue.dv.list_rows', new_callable=AsyncMock)
def test_limpar_reservas_travadas_libera_itens_presos(mock_list_rows, mock_update_row):
    mock_list_rows.return_value = [{'cr85a_redminequeueid': 'row-1', 'cr85a_correlationid': 'corr-1'}]

    total = _run(module.limpar_reservas_travadas(ENV, timeout_minutos=15))

    assert total == 1
    mock_update_row.assert_awaited_once_with(
        ENV, 'cr85a_redminequeues', 'row-1', {'cr85a_status': module.STATUS_PENDING, 'cr85a_reservedat': None},
    )


@patch('app.services.redmine_sync_queue.dv.resolver_entity_set_name', new=AsyncMock(side_effect=_resolver_entity_set))
@patch('app.services.redmine_sync_queue.dv.update_row', new_callable=AsyncMock)
@patch('app.services.redmine_sync_queue.criar_issue_generica')
def test_processar_fila_dry_run_nao_chama_redmine_nem_grava(mock_criar_issue, mock_update_row):
    async def _list_rows(_env, entity_set, *, filtro=None, select=None, top=50, orderby=None):
        if 'PROCESSING' in (filtro or ''):
            return []
        if 'PENDING' in (filtro or ''):
            return [{'cr85a_redminequeueid': 'row-1', 'cr85a_correlationid': 'corr-1', 'cr85a_subject': 'HU-001'}]
        return []

    with patch('app.services.redmine_sync_queue.dv.list_rows', new=AsyncMock(side_effect=_list_rows)):
        resultado = _run(module.processar_fila_redmine(ENV, dry_run=True))

    assert resultado['dry_run'] is True
    assert resultado['enviado'] is False
    assert resultado['seriam_processados'] == [{'row_id': 'row-1', 'correlation_id': 'corr-1', 'subject': 'HU-001'}]
    mock_criar_issue.assert_not_called()
    mock_update_row.assert_not_awaited()


@patch('app.services.redmine_sync_queue.dv.resolver_entity_set_name', new=AsyncMock(side_effect=_resolver_entity_set))
@patch('app.services.redmine_sync_queue.dv.create_row', new_callable=AsyncMock)
@patch('app.services.redmine_sync_queue.dv.update_row', new_callable=AsyncMock)
@patch('app.services.redmine_sync_queue.criar_issue_generica')
def test_processar_fila_sucesso_marca_sent_e_sincroniza_agilesync(mock_criar_issue, mock_update_row, mock_create_row):
    mock_criar_issue.return_value = {'issue_id': 42, 'redmine_url': 'https://redmine/issues/42'}

    async def _list_rows(_env, entity_set, *, filtro=None, select=None, top=50, orderby=None):
        if entity_set == 'cr85a_redminequeues' and 'PROCESSING' in (filtro or ''):
            return []
        if entity_set == 'cr85a_redminequeues' and 'PENDING' in (filtro or ''):
            return [{
                'cr85a_redminequeueid': 'row-1', 'cr85a_correlationid': 'corr-1',
                'cr85a_subject': 'HU-001', 'cr85a_trackerid': 9, 'cr85a_retrycount': 0,
            }]
        if entity_set == 'cr85a_agilesyncs':
            return [{'cr85a_agilesyncid': 'agile-1'}]
        return []

    with patch('app.services.redmine_sync_queue.dv.list_rows', new=AsyncMock(side_effect=_list_rows)):
        resultado = _run(module.processar_fila_redmine(ENV))

    assert resultado['criados'] == 1
    assert resultado['falhas'] == 0
    assert resultado['itens'][0]['redmine_issue_id'] == 42
    mock_criar_issue.assert_called_once_with(subject='HU-001', tracker_id=9)

    status_updates = [c.args[3] for c in mock_update_row.await_args_list if c.args[1] == 'cr85a_redminequeues']
    assert {'cr85a_status': module.STATUS_SENT} in status_updates

    agilesync_updates = [c.args[3] for c in mock_update_row.await_args_list if c.args[1] == 'cr85a_agilesyncs']
    assert {'cr85a_plannerstatus': module.AGILESYNC_STATUS_SYNCED} in agilesync_updates


@patch('app.services.redmine_sync_queue.dv.resolver_entity_set_name', new=AsyncMock(side_effect=_resolver_entity_set))
@patch('app.services.redmine_sync_queue.dv.create_row', new_callable=AsyncMock)
@patch('app.services.redmine_sync_queue.dv.update_row', new_callable=AsyncMock)
@patch('app.services.redmine_sync_queue.criar_issue_generica')
def test_processar_fila_falha_redmine_incrementa_tentativas_e_mascara_erro(mock_criar_issue, mock_update_row, mock_create_row):
    mock_criar_issue.side_effect = IntegracaoError("HTTP 401: {'X-Redmine-API-Key': 'segredo-xyz'}")

    async def _list_rows(_env, entity_set, *, filtro=None, select=None, top=50, orderby=None):
        if entity_set == 'cr85a_redminequeues' and 'PROCESSING' in (filtro or ''):
            return []
        if entity_set == 'cr85a_redminequeues' and 'PENDING' in (filtro or ''):
            return [{
                'cr85a_redminequeueid': 'row-1', 'cr85a_correlationid': 'corr-1',
                'cr85a_subject': 'HU-001', 'cr85a_trackerid': 9, 'cr85a_retrycount': 4,
            }]
        return []

    with patch('app.services.redmine_sync_queue.dv.list_rows', new=AsyncMock(side_effect=_list_rows)):
        resultado = _run(module.processar_fila_redmine(ENV, max_tentativas=5))

    assert resultado['falhas'] == 1
    item = resultado['itens'][0]
    assert item['status'] == module.STATUS_ERROR  # 4 + 1 == max_tentativas
    assert 'segredo-xyz' not in item['erro']

    ultima_chamada_status = [
        c.args[3] for c in mock_update_row.await_args_list
        if c.args[1] == 'cr85a_redminequeues' and 'cr85a_retrycount' in c.args[3]
    ]
    assert ultima_chamada_status[-1]['cr85a_retrycount'] == 5


@patch('app.services.redmine_sync_queue.dv.metadados_coluna', new_callable=AsyncMock)
def test_diagnosticar_coluna_delega_para_dataverse_client(mock_metadados):
    mock_metadados.return_value = {'logical_name': 'cr85a_correlationid', 'attribute_type': 'String', 'max_length': 20}

    resultado = _run(module.diagnosticar_coluna(ENV, 'cr85a_agilesync', 'cr85a_correlationid'))

    assert resultado['max_length'] == 20
    mock_metadados.assert_awaited_once_with(ENV, 'cr85a_agilesync', 'cr85a_correlationid')
