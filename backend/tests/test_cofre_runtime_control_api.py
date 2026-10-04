from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import cofre_runtime_control as runtime_control
from app.db import SessionLocal
from app.main import app
from app.models.auditoria import AuditoriaEvento

client = TestClient(app)
ADMIN_EMAIL = "ericsonjosedossantos@tieri659.onmicrosoft.com"
SHA = "a" * 40


def _admin_headers(correlation_id: str) -> dict[str, str]:
    login = client.post("/v1/auth/login", json={"email": ADMIN_EMAIL})
    token = login.json()["data"]["access_token"]
    return {
        "Authorization": f"Bearer {token}",
        "X-Correlation-Id": correlation_id,
    }


def _clean_audit(correlation_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(AuditoriaEvento).filter(
            AuditoriaEvento.correlation_id == correlation_id
        ).delete()
        db.commit()
    finally:
        db.close()


def _enable_dev(monkeypatch) -> None:
    monkeypatch.setenv("REQSYS_RUNTIME_ENVIRONMENT", "dev")
    monkeypatch.setenv("COFRE_RUNTIME_SELF_RESTART_ENABLED", "1")
    monkeypatch.setenv("GITHUB_SHA", SHA)


def test_control_status_requires_authentication():
    response = client.get("/v1/cofre/runtime/control-status")
    assert response.status_code == 401


def test_control_status_reports_exact_dev_sha(monkeypatch):
    _enable_dev(monkeypatch)
    response = client.get(
        "/v1/cofre/runtime/control-status",
        headers=_admin_headers("corr-runtime-status"),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["environment"] == "dev"
    assert data["runtime_target"] == "pc24x7"
    assert data["runtime_sha"] == SHA
    assert data["self_restart_enabled"] is True
    assert data["boot_id"]
    assert data["production_touched"] is False
    assert data["sensitive_values_exposed"] is False


def test_restart_rejects_non_dev(monkeypatch):
    monkeypatch.setenv("REQSYS_RUNTIME_ENVIRONMENT", "prod")
    monkeypatch.setenv("COFRE_RUNTIME_SELF_RESTART_ENABLED", "1")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    response = client.post(
        "/v1/cofre/runtime/restart",
        json={"expected_sha": SHA, "confirm": "RESTART-COFRE-DEV-RUNTIME"},
        headers=_admin_headers("corr-runtime-prod-deny"),
    )
    assert response.status_code == 403


def test_restart_rejects_disabled_runtime(monkeypatch):
    monkeypatch.setenv("REQSYS_RUNTIME_ENVIRONMENT", "dev")
    monkeypatch.setenv("COFRE_RUNTIME_SELF_RESTART_ENABLED", "0")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    response = client.post(
        "/v1/cofre/runtime/restart",
        json={"expected_sha": SHA, "confirm": "RESTART-COFRE-DEV-RUNTIME"},
        headers=_admin_headers("corr-runtime-disabled-deny"),
    )
    assert response.status_code == 409


def test_restart_rejects_sha_drift_without_scheduling(monkeypatch):
    _enable_dev(monkeypatch)
    scheduled: list[bool] = []
    monkeypatch.setattr(
        runtime_control,
        "schedule_runtime_restart",
        lambda delay_seconds=1.5: scheduled.append(True),
    )
    response = client.post(
        "/v1/cofre/runtime/restart",
        json={"expected_sha": "b" * 40, "confirm": "RESTART-COFRE-DEV-RUNTIME"},
        headers=_admin_headers("corr-runtime-sha-deny"),
    )
    assert response.status_code == 409
    assert scheduled == []


def test_restart_requires_exact_confirmation(monkeypatch):
    _enable_dev(monkeypatch)
    response = client.post(
        "/v1/cofre/runtime/restart",
        json={"expected_sha": SHA, "confirm": "RESTART"},
        headers=_admin_headers("corr-runtime-confirm-deny"),
    )
    assert response.status_code == 422


def test_restart_is_audited_and_replay_is_idempotent(monkeypatch):
    _enable_dev(monkeypatch)
    correlation_id = "corr-runtime-restart-idempotent"
    _clean_audit(correlation_id)
    scheduled: list[float] = []
    monkeypatch.setattr(
        runtime_control,
        "schedule_runtime_restart",
        lambda delay_seconds=1.5: scheduled.append(delay_seconds),
    )

    payload = {"expected_sha": SHA, "confirm": "RESTART-COFRE-DEV-RUNTIME"}
    headers = _admin_headers(correlation_id)

    first = client.post("/v1/cofre/runtime/restart", json=payload, headers=headers)
    assert first.status_code == 202
    first_data = first.json()["data"]
    assert first_data["accepted"] is True
    assert first_data["duplicate"] is False
    assert first_data["restart_scheduled"] is True
    assert scheduled == [1.5]

    replay = client.post("/v1/cofre/runtime/restart", json=payload, headers=headers)
    assert replay.status_code == 202
    replay_data = replay.json()["data"]
    assert replay_data["accepted"] is False
    assert replay_data["duplicate"] is True
    assert replay_data["restart_scheduled"] is False
    assert scheduled == [1.5]

    db = SessionLocal()
    try:
        events = (
            db.query(AuditoriaEvento)
            .filter(
                AuditoriaEvento.correlation_id == correlation_id,
                AuditoriaEvento.acao == "COFRE_RUNTIME_RESTART_REQUESTED",
            )
            .all()
        )
        assert len(events) == 1
        assert events[0].entidade_id == SHA
        assert "production_touched" in (events[0].payload_minimo or "")
    finally:
        db.close()
