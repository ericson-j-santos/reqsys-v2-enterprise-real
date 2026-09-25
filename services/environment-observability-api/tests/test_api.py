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


def test_distributed_operational_context_is_propagated():
    response = load_client().get(
        "/health",
        headers={
            "X-Correlation-Id": "corr-gold-001",
            "X-Causation-Id": "evt-parent-001",
            "X-Workflow-Run-Id": "35999999999",
        },
    )
    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "corr-gold-001"
    assert response.headers["x-causation-id"] == "evt-parent-001"
    assert response.headers["x-workflow-run-id"] == "35999999999"


def test_invalid_distributed_context_is_not_echoed():
    response = load_client().get(
        "/health",
        headers={
            "X-Causation-Id": "invalid value with spaces",
            "X-Workflow-Run-Id": "invalid value with spaces",
        },
    )
    assert response.status_code == 200
    assert "x-causation-id" not in response.headers
    assert "x-workflow-run-id" not in response.headers


def test_environment_is_explicit():
    response = load_client("staging").get("/api/v1/environment")
    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == "staging"
    assert payload["logging"]["format"] == "json"
    assert payload["logging"]["correlation_id"] is True
    assert payload["logging"]["causation_id"] is True
    assert payload["logging"]["workflow_run_id"] is True


def test_readiness_can_block_traffic():
    os.environ["READINESS_ENABLED"] = "false"
    response = load_client("production").get("/api/runtime/readiness")
    assert response.status_code == 503
    os.environ["READINESS_ENABLED"] = "true"
