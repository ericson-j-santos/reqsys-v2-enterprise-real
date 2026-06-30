from fastapi.testclient import TestClient

from app.main import app


def test_runtime_evidence_ingestion_contract_endpoints_are_available():
    client = TestClient(app)

    for endpoint in (
        '/api/runtime/evidence/artifacts',
        '/api/runtime/evidence/incidents',
        '/api/runtime/evidence/scorecard',
    ):
        response = client.get(endpoint)
        assert response.status_code == 200
        body = response.json()
        assert body['success'] is True
        assert isinstance(body['data'], dict)


def test_runtime_evidence_artifacts_contract_is_ready_for_historical_ingestion():
    response = TestClient(app).get('/api/runtime/evidence/artifacts')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['schema_version'] == '1.1.0'
    assert data['artifact_name'] == 'public-runtime-evidence'
    assert data['ingestion_mode'] in {'contract_stub', 'artifact_hydration'}
    assert data['items'][0]['ingestion_status'] == 'contract_ready'


def test_runtime_evidence_scorecard_contract():
    response = TestClient(app).get('/api/runtime/evidence/scorecard')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['schema_version'] == '1.0.0'
    assert data['service'] == 'reqsys-api'
    assert data['availability_percentual'] == 100.0
    assert data['risk'] == 'low'
    assert data['trend'] == 'stable'
