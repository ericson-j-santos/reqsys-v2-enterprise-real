from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint_exposes_red_contract() -> None:
    client = TestClient(app)
    assert client.get('/health').status_code == 200
    assert client.get('/missing-route').status_code == 404

    response = client.get('/metrics')
    assert response.status_code == 200
    body = response.text
    assert 'environment_observability_http_requests_total' in body
    assert 'environment_observability_http_errors_total' in body
    assert 'environment_observability_http_request_duration_seconds' in body
    assert 'route="/health"' in body
    assert 'route="unmatched"' in body
    assert 'status_class="2xx"' in body
    assert 'status_class="4xx"' in body


def test_environment_contract_announces_low_cardinality_red_metrics() -> None:
    payload = TestClient(app).get('/api/v1/environment').json()
    metrics = payload['metrics']
    assert metrics['format'] == 'prometheus'
    assert metrics['endpoint'] == '/metrics'
    assert metrics['methodology'] == 'RED'
    assert metrics['high_cardinality_labels'] is False
    assert metrics['dimensions'] == ['method', 'route', 'status_class']
