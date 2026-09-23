from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "bootstrap_desktop_runtime_repo.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_desktop_runtime_repo", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_contract_is_fixed_to_dedicated_runtime() -> None:
    assert m.EXPECTED_HOST == "DESKTOP-PDQK954"
    assert m.TARGET_REPOSITORY == "ericson-j-santos/desktop-pc24x7-runtime"
    assert m.TARGET_SHA == "4f71186f3c7636ad80f8bd14c74e3fded28101ec"
    assert m.TARGET_RUNNER == "DESKTOP-PDQK954-runtime"
    assert m.TARGET_LABELS[-2:] == ("pc24x7", "desktop-runtime")


def test_registration_token_is_not_embedded_in_result(monkeypatch, tmp_path: Path) -> None:
    class Runtime:
        EXPECTED_HOST = m.EXPECTED_HOST
        REPOSITORY = m.TARGET_REPOSITORY
        RUNNER_NAME = m.TARGET_RUNNER

        @staticmethod
        def validate_host():
            return m.EXPECTED_HOST

        @staticmethod
        def default_runner_home():
            return tmp_path / "runner"

        @staticmethod
        def runner_contract(path):
            return False

        @staticmethod
        def ensure_runner_binaries(path):
            path.mkdir(parents=True, exist_ok=True)

        @staticmethod
        def _register_runner_with_token(path, token):
            assert token == "x" * 32
            (path / ".runner").write_text("opaque", encoding="utf-8")

        @staticmethod
        def start_runner(path):
            return True

        @staticmethod
        def runner_running(path):
            return True

    monkeypatch.setattr(m, "verify_checkout", lambda path: None)
    monkeypatch.setattr(m, "load_runtime_module", lambda path: Runtime)
    states = iter([
        {"present": False, "status": "missing", "labels": [], "labels_ok": False},
        {"present": True, "status": "online", "labels": list(m.TARGET_LABELS), "labels_ok": True},
    ])
    monkeypatch.setattr(m, "snapshot", lambda token, requester=m.request_json: next(states))
    monkeypatch.setattr(m, "registration_token", lambda token, requester=m.request_json: "x" * 32)
    monkeypatch.setattr(
        m,
        "wait_online",
        lambda token, requester=m.request_json, timeout_seconds=45.0: {
            "present": True,
            "status": "online",
            "labels": list(m.TARGET_LABELS),
            "labels_ok": True,
        },
    )

    result = m.bootstrap(tmp_path, "governed-admin-token")
    assert result["ok"] is True
    assert result["runner_registered_now"] is True
    assert result["registration_token_persisted"] is False
    assert result["registration_token_logged"] is False
    assert "governed-admin-token" not in str(result)
    assert "x" * 32 not in str(result)


def test_existing_local_runner_without_registry_fails_closed(monkeypatch, tmp_path: Path) -> None:
    class Runtime:
        EXPECTED_HOST = m.EXPECTED_HOST
        REPOSITORY = m.TARGET_REPOSITORY
        RUNNER_NAME = m.TARGET_RUNNER

        @staticmethod
        def validate_host():
            return m.EXPECTED_HOST

        @staticmethod
        def default_runner_home():
            path = tmp_path / "runner"
            path.mkdir(parents=True, exist_ok=True)
            return path

        @staticmethod
        def runner_contract(path):
            return True

    monkeypatch.setattr(m, "verify_checkout", lambda path: None)
    monkeypatch.setattr(m, "load_runtime_module", lambda path: Runtime)
    monkeypatch.setattr(
        m,
        "snapshot",
        lambda token, requester=m.request_json: {
            "present": False,
            "status": "missing",
            "labels": [],
            "labels_ok": False,
        },
    )
    with pytest.raises(m.BridgeError, match="local_runner_registry_diverged"):
        m.bootstrap(tmp_path, "governed-admin-token")


def test_api_request_keeps_token_only_in_authorization_header() -> None:
    request = m.api_request("secret-value", "/repos/example/example/actions/runners")
    headers = {key.casefold(): value for key, value in request.header_items()}
    assert headers["authorization"] == "Bearer secret-value"
    assert "secret-value" not in request.full_url
