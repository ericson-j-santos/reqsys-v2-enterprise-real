import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def token(client):
    resp = client.post("/v1/auth/login", json={"email": "ericsonjosedossantos@tieri659.onmicrosoft.com", "senha": "admin123"})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]

@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def correlation_id():
    return "corr-test-00001"

