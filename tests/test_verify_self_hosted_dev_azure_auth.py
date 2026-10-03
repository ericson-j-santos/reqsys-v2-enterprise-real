"""Offline contracts; synthetic tokens and stub APIs never prove a live login."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import pytest

FILE = Path(__file__).resolve().parents[1] / "scripts/verify_self_hosted_dev_azure_auth.py"
SPEC = importlib.util.spec_from_file_location("fixed_dev_azure_proof", FILE)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

SOURCE_SHA = "a" * 40
NOW = 1_800_000_000
PUBLIC = {
    "azure_tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "azure_client_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "expected_redirect_uri": m.REDIRECT,
    "demo_login_enabled": False,
}
AUTHZ = "rbac-" + "c" * 16


def b64url(value):
    raw = value if isinstance(value, bytes) else m.canonical(value)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def token(changes=None):
    claims = {
        "aud": PUBLIC["azure_client_id"], "tid": PUBLIC["azure_tenant_id"],
        "iss": "https://login.microsoftonline.com/" + PUBLIC["azure_tenant_id"] + "/v2.0",
        "iat": NOW - 300, "nbf": NOW - 300, "exp": NOW + 1800,
        "preferred_username": "PRIVATE-IDENTITY-NEVER-PRINT",
    }
    claims.update(changes or {})
    return ".".join((
        b64url({"alg": "RS256", "kid": "synthetic-unit-key"}),
        b64url(claims), b64url(b"\x01" * 256),
    ))


def state(id_token=None, *, record_changes=None, duplicate=False):
    record = {
        "credentialType": "IdToken", "clientId": PUBLIC["azure_client_id"],
        "realm": PUBLIC["azure_tenant_id"], "environment": "login.windows.net",
        "secret": token() if id_token is None else id_token,
    }
    record.update(record_changes or {})
    entry = {"name": "msal-idtoken-test", "value": json.dumps(record)}
    bundle = {
        "schemaVersion": 1, "origin": "https://old-authorized-origin.example",
        "storageState": {"cookies": [{"value": "PRIVATE-COOKIE-UNUSED"}]},
        "sessionStorage": [
            # Invalid JSON is deliberate: refresh entries must never be parsed.
            {"name": "msal-refreshtoken-test", "value": "PRIVATE-REFRESH-NOT-JSON"},
            entry,
        ],
    }
    if duplicate:
        bundle["sessionStorage"].append(dict(entry))
    return base64.b64encode(m.canonical(bundle)).decode("ascii")


def envelope(data, success=True):
    return {"success": success, "data": data, "errors": []}


class FakeApi:
    def __init__(self, *, login_success=True, session_success=True,
                 anonymous=401, invalid=401, session_changes=None):
        self.login_success, self.session_success = login_success, session_success
        self.anonymous, self.invalid = anonymous, invalid
        self.session_changes = session_changes or {}
        self.azure_calls = 0
        self.calls = []

    def call(self, path, *, payload=None, bearer=None):
        self.calls.append((path, payload, bearer))
        if path == "/api/runtime/build-info":
            return 200, {"build_sha": SOURCE_SHA}
        if path == "/api/v1/auth/config":
            return 200, envelope({**PUBLIC, "azure_enabled": True,
                                  "auth_status": "ready", "environment": "desenvolvimento"})
        if path == "/api/v1/auth/session" and bearer is None:
            return self.anonymous, {}
        if path == "/api/v1/auth/azure":
            self.azure_calls += 1
            if self.azure_calls == 1:
                assert payload["id_token"] != token()
                return self.invalid, {}
            return 200, envelope({
                "access_token": "PRIVATE-BACKEND-BEARER-NEVER-PRINT-" + "x" * 40,
                "token_type": "bearer",
                "usuario": {"email": "PRIVATE-EMAIL-NEVER-PRINT", "session_epoch": 0,
                            "authz_version": AUTHZ},
            }, self.login_success)
        if path == "/api/v1/auth/session":
            return 200, envelope({
                "papel": "viewer", "permissoes": [], "session_epoch": 0,
                "authz_version": AUTHZ, **self.session_changes,
            }, self.session_success)
        pytest.fail("route was not closed")


@pytest.mark.parametrize("encoded,code", (
    ("", "explicit_msal_state_missing"),
    ("not-base64", "explicit_msal_state_invalid"),
    (base64.b64encode(b'{"schemaVersion":1,"sessionStorage":[]}').decode("ascii"),
     "msal_id_token_not_unique_for_target"),
))
def test_missing_or_invalid_explicit_state_is_blocked(encoded, code):
    with pytest.raises(m.ProofError, match=code):
        m.supplied_id_token(encoded, PUBLIC, NOW)


@pytest.mark.parametrize("changes,code", (
    ({"exp": NOW}, "msal_id_token_expired_or_future"),
    ({"exp": NOW - 1}, "msal_id_token_expired_or_future"),
    ({"nbf": NOW + 1}, "msal_id_token_expired_or_future"),
    ({"iat": NOW + 1}, "msal_id_token_expired_or_future"),
    ({"exp": True}, "msal_id_token_expired_or_future"),
    ({"aud": "cccccccc-cccc-cccc-cccc-cccccccccccc"}, "msal_id_token_binding_invalid"),
    ({"tid": "cccccccc-cccc-cccc-cccc-cccccccccccc"}, "msal_id_token_binding_invalid"),
    ({"iss": "https://untrusted.example/tenant"}, "msal_id_token_issuer_invalid"),
))
def test_wrong_or_expired_claims_never_reach_backend(changes, code):
    api = FakeApi()
    with pytest.raises(m.ProofError, match=code):
        m.verify_backend(api, state(token(changes)), PUBLIC, NOW)
    assert api.calls == []


def test_refresh_and_cookie_data_are_ignored():
    assert m.supplied_id_token(state(), PUBLIC, NOW) == token()
    with pytest.raises(m.ProofError, match="msal_id_token_not_unique_for_target"):
        m.supplied_id_token(state(duplicate=True), PUBLIC, NOW)
    with pytest.raises(m.ProofError, match="msal_id_token_not_unique_for_target"):
        m.supplied_id_token(state(record_changes={"realm": "wrong-tenant"}), PUBLIC, NOW)


def test_signature_negative_control_changes_signature_only():
    original = token()
    invalid = m.invalid_signature(original)
    assert invalid.split(".")[:2] == original.split(".")[:2]
    assert invalid.split(".")[2] != original.split(".")[2]


@pytest.mark.parametrize("kwargs,code", (
    ({"login_success": False}, "azure_login_not_authenticated"),
    ({"session_success": False}, "api_session_not_authenticated"),
    ({"anonymous": 200}, "anonymous_session_not_rejected"),
    ({"invalid": 200}, "invalid_azure_signature_not_rejected"),
    ({"session_changes": {"authz_version": "wrong"}}, "api_session_contract_invalid"),
    ({"session_changes": {"session_epoch": -1}}, "api_session_contract_invalid"),
    ({"session_changes": {"session_epoch": 1}}, "api_session_contract_invalid"),
))
def test_http_200_is_not_authentication_and_controls_are_required(kwargs, code):
    with pytest.raises(m.ProofError, match=code):
        m.verify_backend(FakeApi(**kwargs), state(), PUBLIC, NOW)


def test_valid_backend_contract_requires_two_negative_controls_and_real_routes():
    api = FakeApi()
    result = m.verify_backend(api, state(), PUBLIC, NOW)
    assert result == {
        "azure_login_status": 200, "api_session_status": 200,
        "anonymous_session_rejected": True, "invalid_azure_signature_rejected": True,
    }
    assert [call[0] for call in api.calls] == [
        "/api/v1/auth/session", "/api/v1/auth/azure",
        "/api/v1/auth/azure", "/api/v1/auth/session",
    ]


@pytest.mark.parametrize("changes", (
    {"azure_enabled": False}, {"auth_status": "misconfigured"},
    {"demo_login_enabled": True}, {"environment": "producao"},
    {"expected_redirect_uri": "https://wrong.example/callback"},
    {"azure_client_id": "not-guid"}, {"azure_tenant_id": ""},
))
def test_target_configuration_is_bound_and_demo_or_production_fail_closed(changes):
    config = {**PUBLIC, "azure_enabled": True, "auth_status": "ready",
              "environment": "desenvolvimento", **changes}
    with pytest.raises(m.ProofError):
        m.validate_public_config(200, envelope(config))
    with pytest.raises(m.ProofError):
        m.validate_public_config(200, envelope(config, False))


def test_proof_contains_no_identity_token_or_cookie_and_hashes_public_config_only():
    result = m.verify_backend(FakeApi(), state(), PUBLIC, NOW)
    restore = {"private_metadata": "backup-proof-only"}
    proof = m.make_proof(
        SOURCE_SHA, PUBLIC, restore, result,
        datetime(2026, 10, 3, 15, tzinfo=timezone.utc), verified=True)
    assert proof["authenticated_flow_verified"] is True
    assert proof["verification_scope"] == "backend_azure_session"
    assert proof["ui_interactive_callback_verified"] is False
    assert proof["auth_config_sha256"] == m.digest(PUBLIC)
    assert proof["restore_proof_sha256"] == m.digest(restore)
    integrity = proof.pop("proof_integrity_sha256")
    assert integrity == m.digest(proof)
    serialized = json.dumps(proof)
    for private in (token(), "PRIVATE-IDENTITY-NEVER-PRINT",
                    "PRIVATE-BACKEND-BEARER", "PRIVATE-EMAIL", "PRIVATE-COOKIE"):
        assert private not in serialized


def test_missing_state_replaces_prior_auth_proof_with_false_and_stdout_is_safe(monkeypatch, tmp_path, capsys):
    writes = []
    class Private:
        def evidence(self, path, content):
            writes.append((path, json.loads(content)))
    monkeypatch.setattr(m, "source_context", lambda _: (tmp_path, tmp_path, Private(), {"restore": "bound"}))
    monkeypatch.setattr(m, "validate_candidate", lambda _: None)
    monkeypatch.setattr(m, "FixedApi", FakeApi)
    monkeypatch.delenv(m.SECRET_ENV, raising=False)
    assert m.main(["--source-sha", SOURCE_SHA, "--confirm", m.CONFIRM]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "status": "blocked", "code": "explicit_msal_state_missing",
        "authenticated_flow_verified": False, "ui_interactive_callback_verified": False,
    }
    assert len(writes) == 1 and writes[0][0] == tmp_path / "auth-proof.json"
    assert writes[0][1]["authenticated_flow_verified"] is False
    assert writes[0][1]["azure_login_status"] == 0


def test_fixed_api_rejects_arbitrary_routes_without_network():
    api = m.FixedApi()
    with pytest.raises(m.ProofError, match="api_route_not_closed"):
        api.call("https://attacker.example")
    with pytest.raises(m.ProofError, match="api_route_not_closed"):
        api.call("/api/v1/auth/login", payload={})
    with pytest.raises(m.ProofError, match="bearer_route_not_closed"):
        api.call("/api/v1/auth/config", bearer="unused")


def test_source_validation_runs_before_secret_or_authentication(monkeypatch):
    def blocked(_):
        raise m.ProofError("source_binding_invalid")
    monkeypatch.setattr(m, "source_context", blocked)
    monkeypatch.setattr(m, "FixedApi", lambda: pytest.fail("no HTTP before validated source"))
    with pytest.raises(m.ProofError, match="source_binding_invalid"):
        m.execute(SOURCE_SHA)


def test_child_diagnostics_do_not_receive_explicit_state(monkeypatch, tmp_path):
    from types import SimpleNamespace
    monkeypatch.setenv(m.SECRET_ENV, "PRIVATE-EXPLICIT-STATE")
    observed = {}
    def run(*args, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=b"safe", stderr=b"")
    monkeypatch.setattr(m.subprocess, "run", run)
    assert m.bounded_command(["git", "status"], tmp_path, git=True) == "safe"
    assert m.SECRET_ENV not in observed["env"]
    assert observed["env"]["GIT_OPTIONAL_LOCKS"] == "0"
    assert observed["shell"] is False


def test_main_does_not_print_raw_errors_or_credentials(monkeypatch, capsys):
    def blocked(_):
        raise RuntimeError("PRIVATE-ERROR-TOKEN-IDENTITY")
    monkeypatch.setattr(m, "execute", blocked)
    assert m.main(["--source-sha", SOURCE_SHA, "--confirm", m.CONFIRM]) == 2
    output = capsys.readouterr().out
    assert "PRIVATE" not in output
    assert "authentication_proof_blocked" in output


def test_http_200_false_build_envelope_blocks_before_supplied_secret(monkeypatch, tmp_path):
    class BadBuild(FakeApi):
        def call(self, path, **kwargs):
            if path == "/api/runtime/build-info":
                return 200, envelope({"build_sha": SOURCE_SHA}, False)
            pytest.fail("must not authenticate an unsuccessful build envelope")
    monkeypatch.setattr(m, "source_context", lambda _: (tmp_path, tmp_path, object(), {}))
    monkeypatch.setattr(m, "validate_candidate", lambda _: None)
    monkeypatch.setattr(m, "FixedApi", BadBuild)
    with pytest.raises(m.ProofError, match="candidate_source_sha_mismatch"):
        m.execute(SOURCE_SHA)


def test_candidate_port_is_exact_loopback_with_owned_labels(monkeypatch, tmp_path):
    answers = [
        "d" * 12,
        json.dumps({
            "com.docker.compose.project": m.PROJECT,
            "com.docker.compose.service": "caddy",
            "io.reqsys.selfhost.instance": m.INSTANCE,
        }),
        json.dumps({"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "18080"}]}),
        "true",
    ]
    monkeypatch.setattr(m, "bounded_command", lambda *_args, **_kwargs: answers.pop(0))
    with pytest.raises(m.ProofError, match="candidate_loopback_binding_mismatch"):
        m.validate_candidate(tmp_path)
