from fastapi.testclient import TestClient

from app.main import app


def test_runtime_operational_page_is_available():
    response = TestClient(app).get('/runtime')

    assert response.status_code == 200
    assert 'ReqSys Runtime Operational Page' in response.text
    assert '/api/runtime/health' in response.text
    assert '/api/runtime/contracts' in response.text
