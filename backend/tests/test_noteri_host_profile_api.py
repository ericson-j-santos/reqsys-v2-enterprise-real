from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app

client = TestClient(app)


@pytest.fixture()
def mounted_profile(monkeypatch, tmp_path: Path):
    profile = tmp_path / "host-profile.json"
    audit = tmp_path / "host-profile-api-audit.jsonl"
    monkeypatch.setenv("NOTERI_HOST_PROFILE_PATH", str(profile))
    monkeypatch.setenv("NOTERI_HOST_PROFILE_AUDIT_PATH", str(audit))
    monkeypatch.setenv("NOTERI_HOST_PROFILE_EXPECTED_HOST", "Noteri")
    app.dependency_overrides.clear()
    yield profile, audit
    app.dependency_overrides.clear()


def _admin():
    return {"sub": "admin@teste", "papel": "admin"}


def _analyst():
    return {"sub": "analista@teste", "papel": "analista"}


def test_get_requires_authentication(mounted_profile):
    response = client.get("/v1/noteri/profile")
    assert response.status_code == 401


def test_get_returns_default_normal_when_mount_is_empty(mounted_profile):
    app.dependency_overrides[get_current_user] = _admin
    response = client.get("/v1/noteri/profile")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["host"] == "Noteri"
    assert data["profile"] == "NORMAL"
    assert data["accepts_new_development"] is True


def test_post_requires_admin(mounted_profile):
    app.dependency_overrides[get_current_user] = _analyst
    response = client.post(
        "/v1/noteri/profile",
        headers={"X-Correlation-Id": "corr-study-analyst"},
        json={"profile": "ESTUDO", "correlation_id": "corr-study-analyst"},
    )
    assert response.status_code == 403


def test_estudo_readback_idempotency_and_restore_normal(mounted_profile):
    profile, audit = mounted_profile
    app.dependency_overrides[get_current_user] = _admin

    first = client.post(
        "/v1/noteri/profile",
        headers={"X-Correlation-Id": "corr-study-e2e-001"},
        json={"profile": "ESTUDO", "correlation_id": "corr-study-e2e-001"},
    )
    assert first.status_code == 200
    assert first.json()["data"]["profile"] == "ESTUDO"
    assert first.json()["data"]["accepts_new_development"] is False
    assert first.json()["data"]["changed"] is True

    readback = client.get("/v1/noteri/profile")
    assert readback.status_code == 200
    assert readback.json()["data"]["profile"] == "ESTUDO"
    assert json.loads(profile.read_text(encoding="utf-8"))["profile"] == "ESTUDO"

    replay = client.post(
        "/v1/noteri/profile",
        headers={"X-Correlation-Id": "corr-study-e2e-002"},
        json={"profile": "ESTUDO", "correlation_id": "corr-study-e2e-002"},
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["changed"] is False

    restored = client.post(
        "/v1/noteri/profile",
        headers={"X-Correlation-Id": "corr-study-e2e-003"},
        json={"profile": "NORMAL", "correlation_id": "corr-study-e2e-003"},
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["profile"] == "NORMAL"
    assert restored.json()["data"]["accepts_new_development"] is True
    assert json.loads(profile.read_text(encoding="utf-8"))["profile"] == "NORMAL"

    lines = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert [line["after_profile"] for line in lines] == ["ESTUDO", "ESTUDO", "NORMAL"]


def test_rejects_correlation_mismatch(mounted_profile):
    app.dependency_overrides[get_current_user] = _admin
    response = client.post(
        "/v1/noteri/profile",
        headers={"X-Correlation-Id": "corr-header-001"},
        json={"profile": "ESTUDO", "correlation_id": "corr-body-0001"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "correlation_id_mismatch"


def test_rejects_profile_from_other_host(mounted_profile):
    profile, _ = mounted_profile
    profile.write_text(
        json.dumps({
            "schema_version": "1",
            "host": "DESKTOP-PDQK954",
            "profile": "NORMAL",
            "accepts_new_development": True,
        }),
        encoding="utf-8",
    )
    app.dependency_overrides[get_current_user] = _admin
    response = client.get("/v1/noteri/profile")
    assert response.status_code == 409


def test_missing_mount_fails_closed(monkeypatch, tmp_path: Path):
    monkeypatch.setenv(
        "NOTERI_HOST_PROFILE_PATH",
        str(tmp_path / "missing" / "host-profile.json"),
    )
    monkeypatch.setenv("NOTERI_HOST_PROFILE_EXPECTED_HOST", "Noteri")
    app.dependency_overrides[get_current_user] = _admin
    try:
        response = client.get("/v1/noteri/profile")
        assert response.status_code == 503
        assert "não montado" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
