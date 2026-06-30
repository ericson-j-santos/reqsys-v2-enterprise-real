"""Caminhos críticos — bootstrap main e endpoints runtime legados."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import _build_sha, _runtime_payload, app, warm_database_on_startup


def test_runtime_payload_estrutura():
    payload = _runtime_payload('ok', 'health')
    assert payload['schema_version'] == '1.1.0'
    assert payload['status'] == 'ok'
    assert payload['check'] == 'health'


@patch('app.main.probe_database', return_value=(True, 'ok'))
def test_warm_database_on_startup_sucesso(_probe):
    warm_database_on_startup()


@patch('app.main.probe_database', return_value=(False, 'db down'))
@patch('app.main.settings')
def test_warm_database_on_startup_falha_em_dev(mock_settings, _probe):
    mock_settings.is_production = False
    warm_database_on_startup()


@patch('app.main.probe_database', return_value=(False, 'db down'))
@patch('app.main.settings')
def test_warm_database_on_startup_falha_em_producao(mock_settings, _probe):
    mock_settings.is_production = True
    warm_database_on_startup()


@patch('app.main.probe_database', return_value=(False, 'db down'))
def test_health_retorna_503_quando_banco_indisponivel(_probe):
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 503
    body = response.json()
    assert body['data']['status'] == 'degraded'


def test_build_sha_prioriza_github_e_fallback_fly(monkeypatch):
    monkeypatch.delenv('GITHUB_SHA', raising=False)
    monkeypatch.setenv('FLY_IMAGE_REF', 'registry.example/app:deploy-123')
    assert _build_sha() == 'registry.example/app:deploy-123'

    monkeypatch.setenv('GITHUB_SHA', 'abc123def')
    assert _build_sha() == 'abc123def'


def test_runtime_contracts_e_version():
    client = TestClient(app)
    contracts = client.get('/api/runtime/contracts')
    version = client.get('/api/runtime/version')
    readiness = client.get('/api/runtime/readiness')
    liveness = client.get('/api/runtime/liveness')

    assert contracts.status_code == 200
    data = contracts.json()['data']
    assert data['contract'] == 'reqsys-public-runtime-contract'
    assert data['required_public_endpoints']
    assert version.status_code == 200
    assert version.json()['data']['service'] == 'reqsys-api'
    assert readiness.status_code == 200
    assert readiness.json()['data']['ready'] is True
    assert liveness.status_code == 200
    assert liveness.json()['data']['alive'] is True


def test_runtime_payload_health_check():
    payload = _runtime_payload('ok', 'health')
    assert payload['check'] == 'health'
