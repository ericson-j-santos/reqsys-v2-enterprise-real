from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_runtime_validator_dashboard_has_correlation_id():
    response = client.get(
        "/api/runtime-validator/dashboard", headers={"X-Correlation-ID": "test-cid"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["meta"]["correlation_id"] == "test-cid"
    assert body["data"]["stability_score"] >= 0
    assert body["data"]["governance_events"]


def test_workflow_validation_scores_missing_evidence():
    response = client.post(
        "/api/runtime-validator/workflows/validate",
        json={
            "workflow_name": "CI — ReqSys v2 Enterprise",
            "required_jobs": ["backend", "frontend"],
            "completed_jobs": ["backend"],
            "failed_jobs": [],
            "evidence_urls": [],
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["valid"] is False
    assert data["missing_jobs"] == ["frontend"]
    assert data["stability_score"] == 70


def test_remediation_circuit_breaker_blocks_execute_rollback():
    response = client.post(
        "/api/runtime-validator/remediations",
        json={
            "target": "prod",
            "action": "rollback_release",
            "mode": "execute",
            "max_retries": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["accepted"] is False
    assert data["circuit_breaker_open"] is True
