"""Testes de caminhos críticos — power_automate_provisioning (dispatch e resumo)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

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
