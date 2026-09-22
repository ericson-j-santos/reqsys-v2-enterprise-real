from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.services import noteri_host_profile as profile_service

client = TestClient(app)


@pytest.fixture()
def mounted_profile(monkeypatch, tmp_path: Path):
    profile = tmp_path / "host-profile.json"
    audit = tmp_path / "host-profile-api-audit.jsonl"
    monkeypatch.setenv("NOTERI_HOST_PROFILE_PATH", str(profile))
    monkeypatch.setenv("NOTERI_HOST_PROFILE_AUDIT_PATH", str(audit))
    monkeypatch.setenv("NOTERI_HOST_PROFILE_EXPECTED_HOST", "Noteri")
    monkeypatch.delenv("NOTERI_CONTROL_PLANE_URL", raising=False)
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
        assert response.json()["detail"] == "Perfil do Noteri indisponível."
        assert str(tmp_path) not in response.text
    finally:
        app.dependency_overrides.clear()

def test_control_plane_get_returns_fresh_noteri_profile(monkeypatch):
    monkeypatch.setenv(
        "NOTERI_CONTROL_PLANE_URL",
        "http://host.docker.internal:8787",
    )
    monkeypatch.setenv("NOTERI_HOST_PROFILE_EXPECTED_HOST", "Noteri")
    app.dependency_overrides[get_current_user] = _admin

    def fake_request(method, path, payload=None, *, timeout=5.0):
        assert method == "GET"
        assert path == "/v1/workers"
        assert payload is None
        return {
            "workers": [
                {
                    "worker_id": "noteri",
                    "device_name": "Noteri",
                    "profile": "ESTUDO",
                    "fresh": True,
                    "controller_online": True,
                    "auth_valid": True,
                }
            ]
        }

    monkeypatch.setattr(profile_service, "_control_plane_request", fake_request)
    try:
        response = client.get("/v1/noteri/profile")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["host"] == "Noteri"
        assert data["profile"] == "ESTUDO"
        assert data["accepts_new_development"] is False
        assert data["source"] == "control_plane"
    finally:
        app.dependency_overrides.clear()


def test_control_plane_post_dispatches_fixed_task_and_reads_back(monkeypatch):
    monkeypatch.setenv(
        "NOTERI_CONTROL_PLANE_URL",
        "http://host.docker.internal:8787",
    )
    monkeypatch.setenv("NOTERI_HOST_PROFILE_EXPECTED_HOST", "Noteri")
    app.dependency_overrides[get_current_user] = _admin
    worker_reads = iter(["NORMAL", "ESTUDO"])
    calls = []

    def fake_request(method, path, payload=None, *, timeout=5.0):
        calls.append((method, path, payload))
        if method == "GET" and path == "/v1/workers":
            profile = next(worker_reads)
            return {
                "workers": [
                    {
                        "worker_id": "noteri",
                        "device_name": "Noteri",
                        "profile": profile,
                        "fresh": True,
                        "controller_online": True,
                        "auth_valid": True,
                    }
                ]
            }
        if method == "POST" and path == "/v1/intake":
            assert payload["task_type"] == "host.profile.set.v1"
            assert payload["payload"] == {
                "target_host": "Noteri",
                "profile": "ESTUDO",
                "worker_hint": "builder",
            }
            assert payload["risk"] == 1
            assert payload["max_attempts"] == 1
            return {
                "item": {"id": "item-study-001"},
                "dispatch": {
                    "worker": {
                        "worker_id": "noteri",
                        "device_name": "Noteri",
                    }
                },
            }
        if method == "GET" and path == "/v1/work-items/item-study-001":
            return {
                "item": {
                    "id": "item-study-001",
                    "status": "CONCLUÍDO",
                    "result": {
                        "handler": "host.profile.set.v1",
                        "host": "Noteri",
                        "profile": "ESTUDO",
                        "accepts_new_development": False,
                        "changed": True,
                        "independent_readback": True,
                        "control_plane_readback": True,
                    },
                }
            }
        raise AssertionError((method, path, payload))

    monkeypatch.setattr(profile_service, "_control_plane_request", fake_request)
    try:
        response = client.post(
            "/v1/noteri/profile",
            headers={"X-Correlation-Id": "corr-study-control-001"},
            json={
                "profile": "ESTUDO",
                "correlation_id": "corr-study-control-001",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["profile"] == "ESTUDO"
        assert data["accepts_new_development"] is False
        assert data["changed"] is True
        assert data["source"] == "control_plane"
        intake = next(call for call in calls if call[1] == "/v1/intake")
        assert intake[2]["task_type"] == "host.profile.set.v1"
    finally:
        app.dependency_overrides.clear()


def test_control_plane_estudo_replay_does_not_enqueue(monkeypatch):
    monkeypatch.setenv(
        "NOTERI_CONTROL_PLANE_URL",
        "http://host.docker.internal:8787",
    )
    monkeypatch.setenv("NOTERI_HOST_PROFILE_EXPECTED_HOST", "Noteri")
    app.dependency_overrides[get_current_user] = _admin
    calls = []

    def fake_request(method, path, payload=None, *, timeout=5.0):
        calls.append((method, path, payload))
        if method == "GET" and path == "/v1/workers":
            return {
                "workers": [
                    {
                        "worker_id": "noteri",
                        "device_name": "Noteri",
                        "profile": "ESTUDO",
                        "fresh": True,
                        "controller_online": True,
                        "auth_valid": True,
                    }
                ]
            }
        raise AssertionError((method, path, payload))

    monkeypatch.setattr(profile_service, "_control_plane_request", fake_request)
    try:
        response = client.post(
            "/v1/noteri/profile",
            headers={"X-Correlation-Id": "corr-study-control-002"},
            json={
                "profile": "ESTUDO",
                "correlation_id": "corr-study-control-002",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["profile"] == "ESTUDO"
        assert data["changed"] is False
        assert all(path != "/v1/intake" for _, path, _ in calls)
    finally:
        app.dependency_overrides.clear()


def test_control_plane_stale_worker_fails_closed(monkeypatch):
    monkeypatch.setenv(
        "NOTERI_CONTROL_PLANE_URL",
        "http://host.docker.internal:8787",
    )
    monkeypatch.setenv("NOTERI_HOST_PROFILE_EXPECTED_HOST", "Noteri")
    app.dependency_overrides[get_current_user] = _admin

    monkeypatch.setattr(
        profile_service,
        "_control_plane_request",
        lambda method, path, payload=None, timeout=5.0: {
            "workers": [
                {
                    "worker_id": "noteri",
                    "device_name": "Noteri",
                    "profile": "ESTUDO",
                    "fresh": False,
                    "controller_online": True,
                    "auth_valid": True,
                }
            ]
        },
    )
    try:
        response = client.get("/v1/noteri/profile")
        assert response.status_code == 503
        assert response.json()["detail"] == "Perfil do Noteri indisponível."
    finally:
        app.dependency_overrides.clear()


def test_control_plane_endpoint_is_fail_closed(monkeypatch):
    monkeypatch.setenv(
        "NOTERI_CONTROL_PLANE_URL",
        "http://untrusted.example:8787",
    )
    monkeypatch.setenv("NOTERI_HOST_PROFILE_EXPECTED_HOST", "Noteri")
    app.dependency_overrides[get_current_user] = _admin
    try:
        response = client.get("/v1/noteri/profile")
        assert response.status_code == 503
        assert response.json()["detail"] == "Perfil do Noteri indisponível."
    finally:
        app.dependency_overrides.clear()

