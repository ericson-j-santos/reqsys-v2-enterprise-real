"""Testes de health com probe de banco."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_inclui_status_do_banco():
    response = TestClient(app).get('/health')
    assert response.status_code == 200
    data = response.json()['data']
    assert data['database']['status'] == 'ok'
    assert data['status'] == 'ok'
