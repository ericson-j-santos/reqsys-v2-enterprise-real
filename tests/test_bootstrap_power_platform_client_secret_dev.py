from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_power_platform_client_secret_dev.py"
spec = importlib.util.spec_from_file_location("secret_rotation", SCRIPT)
rotation = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(rotation)


def args(**overrides):
    values = {
        "confirm": rotation.CONFIRMATION,
        "tenant_id": "tenant-dev",
        "client_id": "client-dev",
        "correlation_id": "issue1649-20260916-1",
        "repository": rotation.REPOSITORY,
        "environment": rotation.ENVIRONMENT,
        "secret_name": rotation.SECRET_NAME,
        "days_valid": 90,
        "dry_run": False,
        "skip_validation_dispatch": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def base_mocks(monkeypatch):
    monkeypatch.setattr(rotation, "_resolve_app", lambda *_: ("app-object", "ReqSys Power Platform DEV"))
    monkeypatch.setattr(rotation, "_github_ready", lambda *_: None)
    monkeypatch.setattr(rotation, "_find_rotation", lambda *_: None)


def test_rejects_non_dev_scope(monkeypatch):
    base_mocks(monkeypatch)
    with pytest.raises(rotation.RotationError, match="dev_scope_violation"):
        rotation.execute(args(environment="production"))


def test_dry_run_does_not_create_credential(monkeypatch):
    base_mocks(monkeypatch)
    monkeypatch.setattr(rotation, "_rotate_password_into_github", lambda *_: pytest.fail("must not rotate in dry-run"))
    result = rotation.execute(args(dry_run=True))
    assert result["status"] == "dry_run"
    assert result["secret_value_exposed"] is False


def test_same_correlation_is_fail_closed_and_idempotent(monkeypatch):
    base_mocks(monkeypatch)
    monkeypatch.setattr(rotation, "_find_rotation", lambda *_: {"keyId": "existing"})
    monkeypatch.setattr(rotation, "_rotate_password_into_github", lambda *_: pytest.fail("must not duplicate credential"))
    result = rotation.execute(args())
    assert result["status"] == "blocked"
    assert result["reason"] == "ROTATION_ALREADY_EXISTS"


def test_secret_is_sent_only_over_stdin_without_captured_output(monkeypatch):
    captured = {}

    class Result:
        returncode = 0

    def fake_subprocess_run(command, **kwargs):
        captured.update(command=command, **kwargs)
        return Result()

    monkeypatch.setattr(rotation, "_tool", lambda name: name)
    monkeypatch.setattr(rotation.subprocess, "run", fake_subprocess_run)

    rotation._set_github_secret(
        rotation.REPOSITORY,
        rotation.ENVIRONMENT,
        rotation.SECRET_NAME,
        "top-secret-value",
    )

    assert captured["command"][0] == "gh"
    assert captured["input"] == "top-secret-value"
    assert captured["stdout"] is rotation.subprocess.DEVNULL
    assert captured["stderr"] is rotation.subprocess.DEVNULL
    assert "top-secret-value" not in " ".join(captured["command"])
    assert "--body" not in captured["command"]


def test_sensitive_subprocess_failure_does_not_echo_secret(monkeypatch):
    class Result:
        returncode = 1

    monkeypatch.setattr(rotation, "_tool", lambda name: name)
    monkeypatch.setattr(rotation.subprocess, "run", lambda *a, **k: Result())

    with pytest.raises(rotation.RotationError, match="^gh_sensitive_operation_failed$") as exc:
        rotation._set_github_secret(
            rotation.REPOSITORY,
            rotation.ENVIRONMENT,
            rotation.SECRET_NAME,
            "do-not-log-this-secret",
        )
    assert "do-not-log-this-secret" not in str(exc.value)


def test_rotation_helper_does_not_return_secret(monkeypatch):
    observed = {}
    monkeypatch.setattr(rotation, "_add_password", lambda *_: ("super-secret", "key-1"))
    monkeypatch.setattr(
        rotation,
        "_set_github_secret",
        lambda repo, env, name, value: observed.update(value=value),
    )
    monkeypatch.setattr(
        rotation,
        "_verify_github_secret",
        lambda *_: {"name": rotation.SECRET_NAME, "updated_at": "2026-09-16T19:00:00Z"},
    )

    key_id, evidence = rotation._rotate_password_into_github(
        "app-object",
        "credential-name",
        90,
        rotation.REPOSITORY,
        rotation.ENVIRONMENT,
        rotation.SECRET_NAME,
    )

    assert observed["value"] == "super-secret"
    assert key_id == "key-1"
    assert evidence["name"] == rotation.SECRET_NAME
    assert "super-secret" not in str((key_id, evidence))


def test_success_rotates_verifies_and_dispatches_without_exposing_secret(monkeypatch):
    base_mocks(monkeypatch)
    monkeypatch.setattr(
        rotation,
        "_rotate_password_into_github",
        lambda *_: (
            "key-1",
            {"name": rotation.SECRET_NAME, "updated_at": "2026-09-16T19:00:00Z"},
        ),
    )
    monkeypatch.setattr(rotation, "_main_sha", lambda *_: "a" * 40)
    monkeypatch.setattr(
        rotation,
        "_dispatch_validation",
        lambda *_: {
            "run_id": 123,
            "head_sha": "a" * 40,
            "status": "queued",
            "url": "https://example.invalid/run/123",
        },
    )

    result = rotation.execute(args())
    assert result["status"] == "rotated"
    assert result["secret_value_exposed"] is False
    assert result["existing_credentials_deleted"] is False
    assert "super-secret" not in str(result)
    assert result["validation"]["run_id"] == 123


def test_github_failure_rolls_back_new_entra_password(monkeypatch):
    removed = []
    monkeypatch.setattr(rotation, "_add_password", lambda *_: ("super-secret", "key-rollback"))
    monkeypatch.setattr(
        rotation,
        "_set_github_secret",
        lambda *_: (_ for _ in ()).throw(rotation.RotationError("gh_sensitive_operation_failed")),
    )
    monkeypatch.setattr(rotation, "_remove_password", lambda app_id, key_id: removed.append((app_id, key_id)))

    with pytest.raises(rotation.RotationError, match="gh_sensitive_operation_failed"):
        rotation._rotate_password_into_github(
            "app-object",
            "credential-name",
            90,
            rotation.REPOSITORY,
            rotation.ENVIRONMENT,
            rotation.SECRET_NAME,
        )
    assert removed == [("app-object", "key-rollback")]


def test_rollback_failure_is_sanitized(monkeypatch):
    monkeypatch.setattr(rotation, "_add_password", lambda *_: ("super-secret", "key-rollback"))
    monkeypatch.setattr(
        rotation,
        "_set_github_secret",
        lambda *_: (_ for _ in ()).throw(rotation.RotationError("gh_sensitive_operation_failed")),
    )
    monkeypatch.setattr(
        rotation,
        "_remove_password",
        lambda *_: (_ for _ in ()).throw(RuntimeError("provider detail must not escape")),
    )

    with pytest.raises(rotation.RotationError, match="^github_write_failed_and_entra_rollback_failed$") as exc:
        rotation._rotate_password_into_github(
            "app-object",
            "credential-name",
            90,
            rotation.REPOSITORY,
            rotation.ENVIRONMENT,
            rotation.SECRET_NAME,
        )
    assert "provider detail" not in str(exc.value)
