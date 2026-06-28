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
