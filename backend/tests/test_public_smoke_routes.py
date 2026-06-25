from fastapi.testclient import TestClient

from app.main import app


def test_public_root_route_exposes_smoke_links():
    res = TestClient(app).get('/')

    assert res.status_code == 200
    body = res.json()
    assert body['success'] is True
    data = body['data']
    assert data['status'] == 'ok'
    assert data['service'] == 'reqsys-api'
    assert data['health'] == '/health'
    assert data['runtime_health'] == '/api/runtime/health'
    assert data['runtime_readiness'] == '/api/runtime/readiness'
    assert data['runtime_liveness'] == '/api/runtime/liveness'
    assert data['runtime_metrics'] == '/api/runtime/metrics'


def test_public_health_route_remains_available():
    res = TestClient(app).get('/health')

    assert res.status_code == 200
    body = res.json()
    assert body['success'] is True
    assert body['data']['status'] == 'ok'
    assert body['data']['service'] == 'reqsys-api'
