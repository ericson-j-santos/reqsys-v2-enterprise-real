"""Testes da API do worker Redmine Sync Queue (/v1/redmine-sync)."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.redmine_sync import require_processar_auth
from app.core.config import settings
from app.core.security import require_admin
from app.core.service_tokens import ServiceAuthContext
from app.main import app

client = TestClient(app)


def _fake_admin():
    return {'papel': 'admin'}


def _fake_ctx():
    return ServiceAuthContext(ator='admin@teste', via_token=False)


@pytest.fixture(autouse=True)
def _configurar_environment_url(monkeypatch):
    monkeypatch.setattr(settings, 'redmine_sync_dataverse_url', 'https://org.crm2.dynamics.com')
    yield


@pytest.fixture
def admin_override():
    app.dependency_overrides[require_admin] = _fake_admin
    yield
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def processar_auth_override():
    app.dependency_overrides[require_processar_auth] = _fake_ctx
    yield
    app.dependency_overrides.pop(require_processar_auth, None)


def test_status_sem_admin_retorna_401_ou_403():
    response = client.get('/v1/redmine-sync/status')

    assert response.status_code in (401, 403)


def test_status_sem_environment_url_retorna_409(admin_override, monkeypatch):
    monkeypatch.setattr(settings, 'redmine_sync_dataverse_url', '')

    response = client.get('/v1/redmine-sync/status')

    assert response.status_code == 409


@patch('app.api.redmine_sync.dv.list_rows', new_callable=AsyncMock)
@patch('app.api.redmine_sync.dv.resolver_entity_set_name', new_callable=AsyncMock)
def test_status_agrega_contagens_por_status(mock_resolver, mock_list_rows, admin_override):
    mock_resolver.return_value = 'cr85a_redminequeues'
    mock_list_rows.side_effect = [
        [{'cr85a_redminequeueid': '1'}, {'cr85a_redminequeueid': '2'}],  # PENDING
        [],  # PROCESSING
        [{'cr85a_redminequeueid': '3'}],  # SENT
        [],  # ERROR
    ]

    response = client.get('/v1/redmine-sync/status')

    assert response.status_code == 200
    body = response.json()['data']
    assert body['contagens']['PENDING'] == 2
    assert body['contagens']['SENT'] == 1
    assert body['saude'] == 'verde'


@patch('app.api.redmine_sync.processar_fila_redmine', new_callable=AsyncMock)
def test_processar_sem_credencial_retorna_401(mock_processar):
    response = client.post('/v1/redmine-sync/processar', json={})

    assert response.status_code == 401
    mock_processar.assert_not_awaited()


@patch('app.api.redmine_sync.processar_fila_redmine', new_callable=AsyncMock)
def test_processar_dry_run_delega_para_o_service(mock_processar, processar_auth_override):
    mock_processar.return_value = {
        'dry_run': True, 'enviado': False, 'reservas_liberadas': 0,
        'total_pendentes_no_lote': 0, 'seriam_processados': [],
    }

    response = client.post('/v1/redmine-sync/processar', json={'dry_run': True})

    assert response.status_code == 200
    assert response.json()['data']['dry_run'] is True
    mock_processar.assert_awaited_once()
    _, kwargs = mock_processar.await_args
    assert kwargs['dry_run'] is True


@patch('app.api.redmine_sync.processar_fila_redmine', new_callable=AsyncMock)
def test_processar_erro_dataverse_vira_502(mock_processar, processar_auth_override):
    from app.services.dataverse_queue_client import DataverseError

    mock_processar.side_effect = DataverseError('HTTP 400 em cr85a_redminequeues')

    response = client.post('/v1/redmine-sync/processar', json={})

    assert response.status_code == 502


@patch('app.api.redmine_sync.diagnosticar_coluna', new_callable=AsyncMock)
def test_diagnostico_coluna_alerta_quando_maxlength_curto(mock_diagnosticar, admin_override):
    mock_diagnosticar.return_value = {'logical_name': 'cr85a_correlationid', 'attribute_type': 'String', 'max_length': 20}

    response = client.get(
        '/v1/redmine-sync/diagnostico/coluna',
        params={'tabela': 'cr85a_agilesync', 'coluna': 'cr85a_correlationid'},
    )

    assert response.status_code == 200
    body = response.json()['data']
    assert body['max_length'] == 20
    assert 'MaxLength atual é 20' in body['alerta']


@patch('app.api.redmine_sync.diagnosticar_coluna', new_callable=AsyncMock)
def test_diagnostico_coluna_sem_alerta_quando_tamanho_suficiente(mock_diagnosticar, admin_override):
    mock_diagnosticar.return_value = {'logical_name': 'cr85a_correlationid', 'attribute_type': 'String', 'max_length': 100}

    response = client.get(
        '/v1/redmine-sync/diagnostico/coluna',
        params={'tabela': 'cr85a_agilesync', 'coluna': 'cr85a_correlationid'},
    )

    assert response.status_code == 200
    assert response.json()['data']['alerta'] is None
