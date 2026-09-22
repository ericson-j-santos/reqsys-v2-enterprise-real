"""Testes de caminhos críticos — power_automate_provisioning (dispatch e resumo)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_pa_provisioning_critical.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

import asyncio

from app.db import Base, SessionLocal, engine
from app.services import power_automate_provisioning as svc


def setup_module():
    Base.metadata.create_all(bind=engine)


def _manifesto():
    return {
        'correlation_id': 'corr-pa-dispatch-001',
        'target': {
            'alm_repository': 'acme/reqsys',
            'environment': 'dev',
            'solution_name': 'ReqSysAutomacao',
        },
        'flow': {
            'display_name': 'ReqSys - Flow Teste',
            'trigger_type': 'HttpRequest',
        },
    }


def test_despachar_workflow_sem_github_pat_retorna_degradado(monkeypatch):
    monkeypatch.setattr(svc.settings, 'github_pat', '')

    resultado = asyncio.run(svc.despachar_workflow_provisionamento(_manifesto()))

    assert resultado['dispatched'] is False
    assert resultado['configured'] is False
    assert 'GITHUB_PAT' in resultado['reason']


@patch('app.services.power_automate_provisioning.httpx.AsyncClient')
def test_despachar_workflow_com_pat_e_http_204(mock_client_cls, monkeypatch):
    monkeypatch.setattr(svc.settings, 'github_pat', 'ghp_test_token')

    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_resp.text = ''
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = asyncio.run(svc.despachar_workflow_provisionamento(_manifesto()))

    assert resultado['dispatched'] is True
    assert resultado['configured'] is True
    assert 'workflow_run_url' in resultado


def test_resumo_registry_provisionamentos_vazio():
    db = SessionLocal()
    try:
        resumo = svc.resumo_registry_provisionamentos(db)
        assert resumo['schema_version'] == '1.0.0'
        assert resumo['total'] >= 0
        assert 'por_status' in resumo
        assert 'por_ambiente' in resumo
    finally:
        db.close()


def test_gerar_manifesto_provisionamento_flow_valida_nome_curto():
    with pytest.raises(ValueError, match='display_name'):
        svc.gerar_manifesto_provisionamento_flow('abc')


def test_gerar_manifesto_provisionamento_flow_sucesso(monkeypatch):
    monkeypatch.setattr(svc.settings, 'github_alm_repo', 'acme/alm')

    manifesto = svc.gerar_manifesto_provisionamento_flow(
        'Flow Operacional QA',
        trigger_type='Manual',
        target_environment='hml',
        dry_run=False,
        correlation_id='corr-manifest-001',
    )

    assert manifesto['correlation_id'] == 'corr-manifest-001'
    assert manifesto['status'] == 'dispatch_requested'
    assert manifesto['target']['alm_repository'] == 'acme/alm'
    assert manifesto['flow']['trigger_type'] == 'Manual'


def test_normalizar_trigger_e_status_invalidos():
    with pytest.raises(ValueError, match='TriggerType'):
        svc.normalizar_trigger_type('Webhook')
    with pytest.raises(ValueError, match='Status invalido'):
        svc.normalizar_status('desconhecido')


def test_to_json_e_from_json_fallback():
    assert svc._to_json({'a': 1}).startswith('{')
    assert svc._from_json('') == {}
    assert svc._from_json('invalid-json') == {'raw': 'invalid-json'}


def test_registrar_e_atualizar_registry_provisionamento():
    db = SessionLocal()
    try:
        manifesto = svc.gerar_manifesto_provisionamento_flow('Flow Registry QA Test')
        manifesto['correlation_id'] = 'corr-registry-critical-001'
        item = svc.registrar_manifesto_provisionamento(
            db,
            manifesto,
            status='dispatched',
            dispatch={'workflow_run_url': 'https://github.com/acme/actions/runs/1'},
        )
        assert item.correlation_id == 'corr-registry-critical-001'
        assert item.status == 'dispatched'

        atualizado = svc.atualizar_status_provisionamento(
            db,
            'corr-registry-critical-001',
            status='succeeded',
            artifact_url='https://artifacts.example/pa.zip',
        )
        assert atualizado.status == 'succeeded'
        assert atualizado.artifact_url == 'https://artifacts.example/pa.zip'

        lista = svc.listar_registry_provisionamentos(db, ambiente=manifesto['target']['environment'], limit=10)
        assert any(entry['correlation_id'] == 'corr-registry-critical-001' for entry in lista)

        resumo = svc.resumo_registry_provisionamentos(db)
        assert resumo['total'] >= 1
        assert resumo['ambientes']
    finally:
        db.close()


def test_atualizar_status_provisionamento_inexistente():
    db = SessionLocal()
    try:
        with pytest.raises(ValueError, match='nao encontrado'):
            svc.atualizar_status_provisionamento(db, 'corr-inexistente-xyz', status='failed')
    finally:
        db.close()


@patch('app.services.power_automate_provisioning.httpx.AsyncClient')
def test_despachar_workflow_http_erro_retorna_payload_degradado(mock_client_cls, monkeypatch):
    monkeypatch.setattr(svc.settings, 'github_pat', 'ghp_test_token')

    mock_resp = MagicMock()
    mock_resp.status_code = 422
    mock_resp.text = 'validation failed'
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = asyncio.run(svc.despachar_workflow_provisionamento(_manifesto()))

    assert resultado['dispatched'] is False
    assert resultado['configured'] is True
    assert resultado['status_code'] == 422


@patch('app.services.power_automate_provisioning.httpx.AsyncClient')
def test_despachar_workflow_excecao_retorna_erro(mock_client_cls, monkeypatch):
    monkeypatch.setattr(svc.settings, 'github_pat', 'ghp_test_token')
    mock_client_cls.side_effect = RuntimeError('rede indisponivel')

    resultado = asyncio.run(svc.despachar_workflow_provisionamento(_manifesto()))

    assert resultado['dispatched'] is False
    assert 'rede indisponivel' in resultado['error']
