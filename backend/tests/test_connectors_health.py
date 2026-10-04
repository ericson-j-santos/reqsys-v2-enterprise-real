from fastapi.testclient import TestClient

from app.main import app


def test_connectors_health_status_200():
    res = TestClient(app).get('/api/connectors/health')
    assert res.status_code == 200
    body = res.json()
    assert body['success'] is True
    data = body['data']
    assert isinstance(data['conectores'], list)
    assert len(data['conectores']) >= 1
    assert data['resumo']['total'] == len(data['conectores'])


def test_connectors_health_propaga_correlation_id():
    correlation_id = 'corr-connectors-test'
    res = TestClient(app).get('/api/connectors/health', headers={'X-Correlation-Id': correlation_id})
    assert res.status_code == 200
    body = res.json()
    assert body['meta']['correlation_id'] == correlation_id
    assert body['data']['correlation_id'] == correlation_id
