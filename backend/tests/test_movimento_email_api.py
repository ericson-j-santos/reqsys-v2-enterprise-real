"""Testes da API /v1/movimento-email (Funcionalidade #2861)."""
import pytest
from fastapi.testclient import TestClient

from app.api.movimento_email import require_consumir_auth, require_job_auth
from app.core.config import settings
from app.core.security import require_admin
from app.core.service_tokens import ServiceAuthContext
from app.main import app

client = TestClient(app)


def _fake_admin():
    return {'papel': 'admin'}


def _fake_ctx():
    return ServiceAuthContext(ator='admin@teste', via_token=False)


@pytest.fixture
def admin_override():
    app.dependency_overrides[require_admin] = _fake_admin
    yield
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def job_auth_override():
    app.dependency_overrides[require_job_auth] = _fake_ctx
    yield
    app.dependency_overrides.pop(require_job_auth, None)


@pytest.fixture
def consumir_auth_override():
    app.dependency_overrides[require_consumir_auth] = _fake_ctx
    yield
    app.dependency_overrides.pop(require_consumir_auth, None)


def test_status_sem_admin_retorna_401_ou_403():
    response = client.get('/v1/movimento-email/status')

    assert response.status_code in (401, 403)


def test_status_com_admin_retorna_contagens(admin_override):
    response = client.get('/v1/movimento-email/status')

    assert response.status_code == 200
    body = response.json()
    assert body['success'] is True
    assert 'contagens' in body['data']
    assert body['data']['saude'] in ('verde', 'azul', 'vermelho')


def test_job_executar_sem_auth_retorna_401_ou_403():
    response = client.post('/v1/movimento-email/jobs/executar')

    assert response.status_code in (401, 403)


def test_job_executar_sem_dsn_configurado_retorna_409(job_auth_override, monkeypatch):
    monkeypatch.setattr(settings, 'movimento_email_source_dsn', '')

    response = client.post('/v1/movimento-email/jobs/executar')

    assert response.status_code == 409


def test_fila_consumir_dry_run_nao_exige_smtp_configurado(consumir_auth_override, monkeypatch):
    monkeypatch.setattr(settings, 'movimento_email_smtp_host', '')

    response = client.post('/v1/movimento-email/fila/consumir', json={'dry_run': True})

    assert response.status_code == 200
    body = response.json()
    assert body['data']['dry_run'] is True


def test_fila_consumir_sem_dry_run_sem_smtp_retorna_409(consumir_auth_override, monkeypatch):
    monkeypatch.setattr(settings, 'movimento_email_smtp_host', '')

    response = client.post('/v1/movimento-email/fila/consumir', json={'dry_run': False})

    assert response.status_code == 409
