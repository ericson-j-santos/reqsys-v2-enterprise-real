import importlib
import os

from fastapi.testclient import TestClient


def load_client(environment: str = "development") -> TestClient:
    os.environ["APP_ENV"] = environment
    module = importlib.import_module("app.main")
    module = importlib.reload(module)
    return TestClient(module.app)


def test_health_contract():
    response = load_client().get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.headers["x-correlation-id"]


def test_environment_is_explicit():
    response = load_client("staging").get("/api/v1/environment")
    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == "staging"
    assert payload["logging"]["format"] == "json"
    assert payload["logging"]["correlation_id"] is True


def test_readiness_can_block_traffic():
    os.environ["READINESS_ENABLED"] = "false"
    response = load_client("production").get("/api/runtime/readiness")
    assert response.status_code == 503
    os.environ["READINESS_ENABLED"] = "true"
