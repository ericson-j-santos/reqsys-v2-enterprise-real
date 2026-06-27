"""Testes para o endpoint /api/runtime/production-readiness."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_production_readiness_retorna_200():
    resp = client.get('/api/runtime/production-readiness')
    assert resp.status_code == 200


def test_production_readiness_schema():
    resp = client.get('/api/runtime/production-readiness')
    data = resp.json()
    assert data.get('success') is True
    payload = data.get('data', {})
    assert 'score' in payload
    assert 'passed' in payload
    assert 'total' in payload
    assert 'readiness_level' in payload
    assert 'gates' in payload
    assert isinstance(payload['gates'], list)
    assert payload['total'] > 0


def test_production_readiness_gates_estrutura():
    resp = client.get('/api/runtime/production-readiness')
    gates = resp.json()['data']['gates']
    required_gates = {
        'jwt_secret_strong',
        'jwt_exp_minutes_positive',
        'cors_no_wildcard',
        'jwt_issuer_set',
        'jwt_audience_set',
        'demo_login_disabled',
        'azure_ad_configured',
        'database_reachable',
    }
    gate_names = {g['gate'] for g in gates}
    assert required_gates.issubset(gate_names), f'Gates faltando: {required_gates - gate_names}'
    for gate in gates:
        assert 'gate' in gate
        assert 'passed' in gate
        assert isinstance(gate['passed'], bool)


def test_production_readiness_score_range():
    resp = client.get('/api/runtime/production-readiness')
    score = resp.json()['data']['score']
    assert 0 <= score <= 100, f'Score fora do intervalo esperado: {score}'


def test_production_readiness_readiness_level_valido():
    resp = client.get('/api/runtime/production-readiness')
    level = resp.json()['data']['readiness_level']
    assert level in {'production_ready', 'acceptable', 'not_ready'}, f'readiness_level inválido: {level!r}'


def test_production_readiness_correlation_id_no_response():
    resp = client.get('/api/runtime/production-readiness')
    assert resp.headers.get('x-correlation-id') is not None


def test_health_endpoint_inclui_database_check():
    resp = client.get('/health')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert 'checks' in data
    assert 'database' in data['checks']
    assert data['checks']['database']['status'] in {'ok', 'error'}


def test_health_endpoint_status_geral():
    resp = client.get('/health')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert 'status' in data
    assert data['status'] in {'ok', 'degraded'}
