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


def test_public_runtime_canonical_routes_are_available():
    client = TestClient(app)

    expected = {
        '/api/runtime/health': ('ok', 'health'),
        '/api/runtime/readiness': ('ready', 'readiness'),
        '/api/runtime/liveness': ('alive', 'liveness'),
    }

    for endpoint, (status, check) in expected.items():
        res = client.get(endpoint)

        assert res.status_code == 200
        body = res.json()
        assert body['success'] is True
        data = body['data']
        assert data['status'] == status
        assert data['check'] == check
        assert data['service'] == 'reqsys-api'
        assert data['environment']
        assert data['version']
        assert data['timestamp']
