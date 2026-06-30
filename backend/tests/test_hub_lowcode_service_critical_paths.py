"""Testes de caminhos críticos — serviço hub_lowcode (degradação e persistência)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_hub_lowcode_service.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.db import Base, SessionLocal, engine
from app.services import hub_lowcode as svc

import asyncio


@pytest.fixture(scope='module', autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def _run(coro):
    return asyncio.run(coro)


def test_listagens_sem_credenciais_retornam_configurado_false(monkeypatch):
    monkeypatch.setattr(svc.settings, 'azure_tenant_id', '')
    monkeypatch.setattr(svc.settings, 'azure_client_id', '')
    monkeypatch.setattr(svc.settings, 'azure_client_secret', '')
    monkeypatch.setattr(svc.settings, 'sharepoint_site_id', '')
    monkeypatch.setattr(svc.settings, 'github_alm_repo', '')

    pacotes = _run(svc.listar_pacotes_ia())
    flows = _run(svc.listar_flows_pa())
    ambientes = _run(svc.listar_ambientes_powerplatform())
    github = _run(svc.listar_runs_github())
    planos = _run(svc.descobrir_planos_planner('group-1'))

    assert pacotes['configurado'] is False
    assert pacotes['itens'] == []
    assert flows['configurado'] is False
    assert ambientes['configurado'] is False
    assert github['configurado'] is False
    assert planos['configurado'] is False


def test_listar_runs_github_sem_repo_configurado(monkeypatch):
    monkeypatch.setattr(svc.settings, 'github_alm_repo', '')
    resultado = _run(svc.listar_runs_github())
    assert resultado['configurado'] is False
    assert 'GITHUB_ALM_REPO' in resultado['erro']


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_listar_runs_github_com_mock(mock_client_cls, monkeypatch):
    monkeypatch.setattr(svc.settings, 'github_alm_repo', 'acme/repo')
    monkeypatch.setattr(svc.settings, 'github_pat', '')

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        'workflow_runs': [
            {
                'id': 99,
                'name': 'CI',
                'path': '.github/workflows/ci.yml',
                'head_branch': 'main',
                'head_sha': 'abcdef1234567890',
                'status': 'completed',
                'conclusion': 'success',
                'created_at': '2026-06-28T00:00:00Z',
                'html_url': 'https://github.com/acme/repo/actions/runs/99',
            }
        ]
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.listar_runs_github(limit=5))

    assert resultado['configurado'] is True
    assert len(resultado['runs']) == 1
    assert resultado['runs'][0]['commit'] == 'abcdef12'


def test_status_consolidado_agrega_pacotes_e_github(monkeypatch):
    async def fake_pacotes(limit=1):
        return {'configurado': True, 'itens': [{'id': 'pkg-1'}], 'erro': None}

    async def fake_github(limit=1):
        return {'configurado': True, 'runs': [{'id': 1}], 'erro': None}

    monkeypatch.setattr(svc, 'listar_pacotes_ia', fake_pacotes)
    monkeypatch.setattr(svc, 'listar_runs_github', fake_github)

    resultado = _run(svc.status_consolidado())

    assert resultado['pacotes_configurado'] is True
    assert resultado['ultimo_pacote']['id'] == 'pkg-1'
    assert resultado['github_configurado'] is True
    assert resultado['ultimo_run']['id'] == 1
    assert resultado['gerado_em']


def test_planner_webhook_config_salvar_e_listar_historico():
    db = SessionLocal()
    try:
        svc.salvar_planner_webhook_config(db, webhook_url='', teams_webhook_url='')
        cfg = svc.obter_planner_webhook_config(db)
        assert cfg['configurado'] is False

        salvo = svc.salvar_planner_webhook_config(
            db,
            webhook_url='https://example.com/planner-hook',
            teams_webhook_url='https://example.com/teams-hook',
        )
        assert 'planner_webhook_url' in salvo['salvo']

        cfg2 = svc.obter_planner_webhook_config(db)
        assert cfg2['configurado'] is True
        assert cfg2['teams_configurado'] is True

        svc.salvar_log_integracao(
            db,
            tipo='planner',
            status='sucesso',
            autor='tester',
            mensagem='evento de teste',
            correlation_id='corr-hub-lowcode-001',
        )
        historico = svc.listar_historico_integracoes(db, tipo='planner', limit=10)
        assert historico['total'] >= 1
        assert historico['eventos'][0]['correlation_id'] == 'corr-hub-lowcode-001'
    finally:
        db.close()


def test_publicar_tarefas_planner_sem_webhook_registra_erro():
    db = SessionLocal()
    try:
        svc.salvar_planner_webhook_config(db, webhook_url='')
        resultado = _run(
            svc.publicar_tarefas_planner(
                db,
                tarefas_texto='Tarefa|Dev|2026-06-28|Backlog|Alta|Desc',
                autor='tester',
                correlation_id='corr-planner-sem-webhook',
            )
        )
        assert resultado['ok'] is False
        assert 'Webhook' in resultado['erro']
    finally:
        db.close()


def test_testar_teams_webhook_url_vazia():
    resultado = _run(svc.testar_teams_webhook(''))
    assert resultado['ok'] is False
    assert 'fornecida' in resultado['erro']


def test_try_json_serializa_dict_e_none():
    assert svc._try_json(None) == '{}'
    assert svc._try_json('raw-text') == 'raw-text'
    assert '"a"' in svc._try_json({'a': 1})


def _mock_credenciais_graph(monkeypatch):
    monkeypatch.setattr(svc.settings, 'azure_tenant_id', 'tenant-id')
    monkeypatch.setattr(svc.settings, 'azure_client_id', 'client-id')
    monkeypatch.setattr(svc.settings, 'azure_client_secret', 'client-secret')
    monkeypatch.setattr(svc.settings, 'sharepoint_site_id', 'site-id')


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_listar_pacotes_ia_com_mock_graph(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        'value': [
            {
                'id': 'pkg-1',
                'fields': {
                    'Projeto': 'ReqSys',
                    'Branch': 'main',
                    'CommitHash': 'abcdef1234567890',
                    'TechStack': 'python',
                    'TotalArquivos': 10,
                    'TamanhoPacoteMb': 1.5,
                    'Status': 'ok',
                    'ChaveIdempotencia': 'key-1',
                    'DataGeracaoUtc': '2026-06-28T00:00:00Z',
                    'ProcessadoEmUtc': '2026-06-28T01:00:00Z',
                },
            }
        ]
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock(), json=lambda: {'access_token': 'token'}))
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.listar_pacotes_ia(limit=5))

    assert resultado['configurado'] is True
    assert len(resultado['itens']) == 1
    assert resultado['itens'][0]['projeto'] == 'ReqSys'
    assert resultado['itens'][0]['commit'] == 'abcdef123456'


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_listar_pacotes_ia_degrada_em_excecao(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=RuntimeError('graph indisponivel'))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.listar_pacotes_ia())

    assert resultado['configurado'] is True
    assert resultado['itens'] == []
    assert 'graph indisponivel' in resultado['erro']


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_listar_flows_pa_degrada_em_excecao(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock(), json=lambda: {'access_token': 'token'}))
    mock_client.get = AsyncMock(side_effect=RuntimeError('dataverse offline'))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.listar_flows_pa())

    assert resultado['configurado'] is True
    assert resultado['flows'] == []
    assert 'dataverse offline' in resultado['erro']


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_listar_ambientes_powerplatform_degrada_em_excecao(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock(), json=lambda: {'access_token': 'token'}))
    mock_client.get = AsyncMock(side_effect=RuntimeError('pa offline'))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.listar_ambientes_powerplatform())

    assert resultado['configurado'] is True
    assert resultado['ambientes'] == []
    assert 'pa offline' in resultado['erro']


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_listar_flows_pa_mapeia_status_stopped(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        'value': [
            {
                'workflowid': 'flow-2',
                'name': 'Flow Parado',
                'statuscode': 1,
                'createdon': '2026-06-28T00:00:00Z',
                'modifiedon': '2026-06-28T01:00:00Z',
            }
        ]
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock(), json=lambda: {'access_token': 'token'}))
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.listar_flows_pa())

    assert resultado['flows'][0]['estado'] == 'Stopped'
    _mock_credenciais_graph(monkeypatch)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        'value': [
            {
                'workflowid': 'flow-1',
                'name': 'Flow Teste',
                'statuscode': 2,
                'createdon': '2026-06-28T00:00:00Z',
                'modifiedon': '2026-06-28T01:00:00Z',
            }
        ]
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock(), json=lambda: {'access_token': 'token'}))
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.listar_flows_pa())

    assert resultado['configurado'] is True
    assert resultado['flows'][0]['nome'] == 'Flow Teste'
    assert resultado['flows'][0]['estado'] == 'Started'


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_listar_ambientes_powerplatform_com_mock(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        'value': [
            {
                'name': 'env-1',
                'location': 'brazilsouth',
                'properties': {'displayName': 'Dev', 'environmentSku': 'Standard', 'provisioningState': 'Succeeded'},
            }
        ]
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock(), json=lambda: {'access_token': 'token'}))
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.listar_ambientes_powerplatform())

    assert resultado['configurado'] is True
    assert resultado['ambientes'][0]['nome'] == 'Dev'


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_descobrir_planos_planner_com_mock(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {'value': [{'id': 'plan-1', 'title': 'Plano QA'}]}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock(), json=lambda: {'access_token': 'token'}))
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.descobrir_planos_planner('group-1'))

    assert resultado['configurado'] is True
    assert resultado['planos'][0]['titulo'] == 'Plano QA'


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_listar_runs_github_com_pat_e_erro_http(mock_client_cls, monkeypatch):
    monkeypatch.setattr(svc.settings, 'github_alm_repo', 'acme/repo')
    monkeypatch.setattr(svc.settings, 'github_pat', 'ghp_test')

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {'workflow_runs': []}
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.listar_runs_github())
    assert resultado['configurado'] is True
    assert resultado['runs'] == []

    mock_client.get = AsyncMock(side_effect=RuntimeError('github offline'))
    resultado_erro = _run(svc.listar_runs_github())
    assert resultado_erro['runs'] == []
    assert 'github offline' in resultado_erro['erro']


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_publicar_tarefas_planner_sucesso(mock_client_cls):
    db = SessionLocal()
    try:
        svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/planner-hook', webhook_key='secret-key')

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {'criadas': 2, 'teams_notificado': True}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resultado = _run(
            svc.publicar_tarefas_planner(
                db,
                tarefas_texto='Tarefa|Dev|2026-06-28|Backlog|Alta|Desc',
                autor='tester',
                correlation_id='corr-planner-ok',
            )
        )

        assert resultado['ok'] is True
        assert resultado['criadas'] == 2
        assert resultado['teams_notificado'] is True
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_publicar_tarefas_planner_http_status_error(mock_client_cls):
    import httpx

    db = SessionLocal()
    try:
        svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/planner-hook')

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError('erro', request=MagicMock(), response=mock_resp)
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resultado = _run(
            svc.publicar_tarefas_planner(
                db,
                tarefas_texto='Tarefa|Dev|2026-06-28|Backlog|Alta|Desc',
                autor='tester',
                correlation_id='corr-planner-http',
            )
        )

        assert resultado['ok'] is False
        assert 'HTTP 500' in resultado['erro']
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_publicar_tarefas_planner_com_webhook_key(mock_client_cls):
    db = SessionLocal()
    try:
        svc.salvar_planner_webhook_config(
            db,
            webhook_url='https://example.com/planner-hook',
            webhook_key='secret-key',
        )

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {'criadas': 1, 'teams_notificado': False}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resultado = _run(
            svc.publicar_tarefas_planner(
                db,
                tarefas_texto='Tarefa|Dev|2026-06-28|Backlog|Alta|Desc',
                autor='tester',
                correlation_id='corr-planner-key',
            )
        )

        assert resultado['ok'] is True
        headers = mock_client.post.await_args.kwargs['headers']
        assert headers['x-webhook-key'] == 'secret-key'
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_descobrir_planos_planner_degrada_em_excecao(mock_client_cls, monkeypatch):
    _mock_credenciais_graph(monkeypatch)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock(), json=lambda: {'access_token': 'token'}))
    mock_client.get = AsyncMock(side_effect=RuntimeError('planner offline'))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = _run(svc.descobrir_planos_planner('group-1'))

    assert resultado['configurado'] is True
    assert resultado['planos'] == []
    assert 'planner offline' in resultado['erro']
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    ok = _run(svc.testar_teams_webhook('https://example.com/teams'))
    assert ok['ok'] is True
    assert ok['status'] == 200

    import httpx

    mock_resp_err = MagicMock()
    mock_resp_err.status_code = 403
    mock_resp_err.text = 'forbidden'
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError('erro', request=MagicMock(), response=mock_resp_err)
    )
    erro = _run(svc.testar_teams_webhook('https://example.com/teams'))
    assert erro['ok'] is False
    assert 'HTTP 403' in erro['erro']


def test_listar_historico_integracoes_filtra_status():
    db = SessionLocal()
    try:
        svc.salvar_log_integracao(db, tipo='planner', status='sucesso', autor='a', correlation_id='c1')
        svc.salvar_log_integracao(db, tipo='planner', status='erro', autor='a', correlation_id='c2')
        historico = svc.listar_historico_integracoes(db, tipo='planner', status='erro', limit=5)
        assert historico['total'] >= 1
        assert all(evento['status'] == 'erro' for evento in historico['eventos'])
    finally:
        db.close()
