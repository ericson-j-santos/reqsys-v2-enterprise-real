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
    assert data['runtime_contracts'] == '/api/runtime/contracts'
    assert data['runtime_version'] == '/api/runtime/version'
    assert data['runtime_build_info'] == '/api/runtime/build-info'
    assert data['runtime_dependencies'] == '/api/runtime/dependencies'
    assert data['requisitos_api'] == '/api/requisitos'
    assert data['requisitos_v1'] == '/v1/requisitos'


def test_public_health_route_remains_available():
    res = TestClient(app).get('/health')

    assert res.status_code == 200
    body = res.json()
    assert body['success'] is True
    assert body['data']['status'] == 'ok'
    assert body['data']['service'] == 'reqsys-api'


def test_public_runtime_json_contracts_are_available():
    client = TestClient(app)

    for endpoint in (
        '/api/runtime/contracts',
        '/api/runtime/version',
        '/api/runtime/build-info',
        '/api/runtime/dependencies',
    ):
        res = client.get(endpoint)
        assert res.status_code == 200
        body = res.json()
        assert body['success'] is True
        assert isinstance(body['data'], dict)


def test_public_runtime_contract_declares_required_endpoints():
    res = TestClient(app).get('/api/runtime/contracts')

    assert res.status_code == 200
    data = res.json()['data']
    assert data['schema_version'] == '1.1.0'
    assert data['contract'] == 'reqsys-public-runtime-contract'

    required_paths = {item['path'] for item in data['required_public_endpoints']}
    assert required_paths == {
        '/health',
        '/api/runtime/health',
        '/api/runtime/readiness',
        '/api/runtime/liveness',
    }

    optional_paths = {item['path'] for item in data['optional_public_evidence']}
    assert '/api/requisitos' in optional_paths
    assert '/api/requisitos/{codigo}' in optional_paths

    for item in data['required_public_endpoints']:
        assert item['method'] == 'GET'
        assert item['expected_http'] == 200
