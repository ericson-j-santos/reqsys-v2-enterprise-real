"""Contratos isolados do E2E Noteri Pages; nao usam identidade real em CI."""
from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE_FILE = SCRIPTS / "noteri_study_mode_pages_e2e.py"
spec = importlib.util.spec_from_file_location("noteri_pages_msalauth_test", MODULE_FILE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def config():
    return {
        "environment": "desenvolvimento",
        "azure_enabled": True,
        "demo_login_enabled": False,
        "expected_redirect_uri": module.PAGES + "/auth/callback.html",
        "azure_client_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "azure_tenant_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    }


def encoded(origin=None):
    state = {
        "schemaVersion": 1,
        "origin": module.PAGES_ORIGIN if origin is None else origin,
        "sessionStorage": [
            {"name": "msal.test-idtoken", "value": "not-a-real-credential"},
            {"name": "reqsys_token", "value": "do-not-import"},
        ],
    }
    return base64.b64encode(json.dumps(state).encode()).decode()


def test_missing_or_wrong_origin_fails_before_browser():
    with pytest.raises(module.E2EBlocked, match="msal_state_missing_or_oversized"):
        module.load_authorized_msal_state(config(), "")
    with pytest.raises(module.E2EBlocked, match="msal_state_wrong_origin_or_schema"):
        module.load_authorized_msal_state(config(), encoded("https://old-dev.example"))


def test_admin_test_state_must_be_explicitly_approved_and_real(monkeypatch):
    seen = []
    def valid(*args):
        seen.append(args[2])
        return "synthetic-only-unit-test"
    monkeypatch.setattr(module.msal_proof, "supplied_id_token", valid)
    items = module.load_authorized_msal_state(config(), encoded())
    assert [item["name"] for item in items] == ["msal.test-idtoken"]
    assert len(seen) == 1


@pytest.mark.parametrize("change", [
    {"environment": "producao"},
    {"azure_enabled": False},
    {"demo_login_enabled": True},
    {"expected_redirect_uri": "https://wrong.example/auth"},
])
def test_environment_or_azure_drift_fails_closed(monkeypatch, change):
    cfg = {**config(), **change}
    with pytest.raises(module.E2EBlocked, match="azure_dev_contract_invalid"):
        module.load_authorized_msal_state(cfg, encoded())


def test_invalid_msalsession_rejected(monkeypatch):
    def refuse(*args):
        raise module.msal_proof.ProofError("invalid")
    monkeypatch.setattr(module.msal_proof, "supplied_id_token", refuse)
    with pytest.raises(module.E2EBlocked, match="msal_state_claims_invalid_or_expired"):
        module.load_authorized_msal_state(config(), encoded())


def test_non_desktop_execution_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(module.socket, "gethostname", lambda: "UNEXPECTED-HOST")
    with pytest.raises(module.E2EBlocked, match="dev_host_or_confirmation_invalid"):
        module.require_exact_environment(tmp_path, "a" * 40, module.CONFIRM)


def test_restoration_is_explicit_and_has_two_independent_readbacks(monkeypatch):
    calls = []
    monkeypatch.setattr(
        module, "post_profile",
        lambda token, profile, cid: calls.append(("post", profile, cid)),
    )
    monkeypatch.setattr(module, "profile", lambda token, expected: calls.append(("api", expected)))
    monkeypatch.setattr(module, "worker", lambda expected: calls.append(("worker", expected)))
    module.restore_normal("synthetic-unit-only", "corr-001")
    assert calls == [
        ("post", "NORMAL", "corr-001-restore"),
        ("api", "NORMAL"),
        ("worker", "NORMAL"),
    ]


def test_restore_failure_keeps_error_and_never_claims_success(monkeypatch):
    def fail(*args):
        raise ValueError("sensitive details")
    monkeypatch.setattr(module, "post_profile", fail)
    with pytest.raises(module.E2EBlocked, match="normal_restore_not_confirmed"):
        module.restore_normal("synthetic-unit-only", "corr-001")


def test_post_preserves_correlation_in_header_and_body(monkeypatch):
    captured = {}
    def http(method, path, **kwargs):
        captured.update(kwargs)
        return 200, {"data": {"host": "Noteri", "profile": "NORMAL", "changed": False}}
    monkeypatch.setattr(module.legacy, "http_json", http)
    module.post_profile("synthetic", "NORMAL", "corr-1000")
    assert captured["body"]["correlation_id"] == captured["correlation_id"]
    assert captured["body"]["profile"] == "NORMAL"


def test_negative_control_precedes_any_mode_change(monkeypatch):
    observed = []
    def http(method, path, *, stage=None, **kwargs):
        observed.append(stage)
        if stage == "unauthenticated_negative":
            return 401, {}
        if stage == "msal_backend_session":
            return 200, {"data": {"papel": "admin"}}
        if stage == "correlation_negative":
            assert kwargs["body"]["correlation_id"] != kwargs["correlation_id"]
            return 409, {}
        raise AssertionError(stage)
    monkeypatch.setattr(module.legacy, "http_json", http)
    monkeypatch.setattr(module, "profile", lambda token, profile: observed.append("api"))
    monkeypatch.setattr(module, "worker", lambda profile: observed.append("worker"))
    module.check_before_mutation("synthetic", "corr-1000")
    assert observed == [
        "unauthenticated_negative", "msal_backend_session",
        "api", "worker", "correlation_negative", "api", "worker",
    ]


def test_run_checks_runtime_before_secret_or_browser(monkeypatch, tmp_path):
    order = []
    monkeypatch.setattr(module, "require_exact_environment", lambda *a: order.append("runtime"))
    monkeypatch.setattr(
        module.legacy, "http_json",
        lambda *a, **kw: (order.append("config") or 200, {"data": config()}),
    )
    monkeypatch.setattr(module, "load_authorized_msal_state", lambda *a: order.append("msal") or [])
    monkeypatch.setattr(module, "browser_e2e", lambda *a: order.append("browser") or {"final_profile": "NORMAL"})
    result = module.run(tmp_path, "a" * 40, module.CONFIRM, "corr-1000")
    assert order == ["runtime", "config", "msal", "browser"]
    assert result["ok"] is True
    assert result["production_touched"] is False


def test_script_never_calls_legacy_mutating_reconciler():
    content = MODULE_FILE.read_text(encoding="utf-8")
    assert "legacy.execute(" not in content
    assert "legacy.api_e2e(" not in content
    assert "legacy.browser_e2e(" not in content
    assert "REQSYS_NOTERI_DEV_MSAL_STATE_B64" in content
    assert "if attempted and not verified and token:" in content
    assert "restore_normal(token, correlation)" in content
