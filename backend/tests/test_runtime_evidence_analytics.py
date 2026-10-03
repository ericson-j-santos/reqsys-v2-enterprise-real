from fastapi.testclient import TestClient

from app.main import app


def test_runtime_evidence_json_endpoints_are_available():
    client = TestClient(app)

    for endpoint in (
        '/api/runtime/evidence/history',
        '/api/runtime/evidence/summary',
        '/api/runtime/evidence/trends',
    ):
        response = client.get(endpoint)
        assert response.status_code == 200
        body = response.json()
        assert body['success'] is True
        assert isinstance(body['data'], dict)


def test_runtime_evidence_summary_contract():
    response = TestClient(app).get('/api/runtime/evidence/summary')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['schema_version'] == '1.0.0'
    assert data['service'] == 'reqsys-api'
    assert data['availability_percentual'] == 100.0
    assert data['required_ok'] == data['required_total']
    assert data['confidence_score'] >= 80


def test_runtime_evidence_page_is_available():
    response = TestClient(app).get('/runtime/evidence')

    assert response.status_code == 200
    assert 'Runtime Evidence Analytics' in response.text
    assert '/api/runtime/evidence/summary' in response.text
