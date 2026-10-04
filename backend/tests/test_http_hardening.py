"""Regressão do hardening HTTP recuperado no PR #25."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


@patch('app.main.probe_database', return_value=(True, 'ok'))
def test_health_live_e_ready_preservam_contrato_operacional(_probe):
    client = TestClient(app)

    live = client.get('/health/live')
    ready = client.get('/health/ready')

    assert live.status_code == 200
    assert live.json()['data'] == {'status': 'alive', 'service': 'reqsys-api'}

    assert ready.status_code == 200
    assert ready.json()['data']['status'] == 'ready'
    assert ready.json()['data']['checks']['database'] == 'ok'


@patch('app.main.probe_database', return_value=(False, 'OperationalError'))
def test_health_ready_falha_fechado_quando_banco_indisponivel(_probe):
    response = TestClient(app).get('/health/ready')

    assert response.status_code == 503
    data = response.json()['data']
    assert data['status'] == 'degraded'
    assert data['checks']['database'] == 'error'
    assert data['database']['detail'] == 'OperationalError'


def test_correlation_id_e_headers_defensivos_sao_propagados():
    correlation_id = 'pr25-hardening-correlation-001'
    client = TestClient(app)

    first = client.get('/health/live', headers={'X-Correlation-ID': correlation_id})
    repeated = client.get('/health/live', headers={'X-Correlation-ID': correlation_id})

    for response in (first, repeated):
        assert response.status_code == 200
        assert response.headers['X-Correlation-ID'] == correlation_id
        assert response.headers['X-Request-ID'] == correlation_id
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert response.headers['X-Frame-Options'] == 'DENY'
        assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
        assert 'camera=()' in response.headers['Permissions-Policy']
        assert 'Strict-Transport-Security' not in response.headers


def test_request_id_tambem_define_correlacao_e_https_recebe_hsts():
    request_id = 'pr25-request-id-001'
    client = TestClient(app, base_url='https://testserver')

    response = client.get('/health/live', headers={'X-Request-ID': request_id})

    assert response.status_code == 200
    assert response.headers['X-Correlation-ID'] == request_id
    assert response.headers['X-Request-ID'] == request_id
    assert response.headers['Strict-Transport-Security'] == 'max-age=31536000; includeSubDomains'
