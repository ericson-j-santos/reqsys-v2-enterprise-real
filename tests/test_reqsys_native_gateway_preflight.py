"""Provas sintéticas de contrato: NUNCA certificam um host físico."""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import reqsys_native_gateway_preflight as native  # noqa: E402
from scripts.validate_reqsys_native_dev_profile import (  # noqa: E402
    NativeAdmissionBlocked,
    REQUIRED_GATES,
    _canonical_bytes,
)

KEY = b"local-test-only-do-not-store-in-production-0123456789"
SHA = "a" * 40
ID = "reqsys-pc-a1b2c3d4"
HOST = "host-physical-a1b2c3d4"
NOW = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
RUN_ID = 987654321


def policy():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def signed(payload):
    return {"payload": payload,
            "signature": hmac.new(KEY, _canonical_bytes(payload), hashlib.sha256).hexdigest()}


def fixture():
    bundle = {
        "schema_version": 1,
        "launcher": {
            "result": "SESSION_LAUNCH_OK", "state_validated": True,
            "head": SHA, "session_id": "session-unique-a1b2c3d4",
            "host": HOST, "profile": "NORMAL",
            "worktree_exclusive": True, "lease_exclusive": True,
        },
        "gateway": {
            "result": "ok", "gateway_exit_code": 0,
            "state_changed": False, "head": SHA,
            "session_id": "session-unique-a1b2c3d4",
            "command_tag": native.COMMAND_TAG,
            "correlation_id": "correlation-native-test-12345",
        },
        "github": {
            "source": "github_rest_independent_readback",
            "run_id": RUN_ID, "runner_instance_id": ID,
            "physical_host_id": HOST,
            "status": "online", "busy": False,
            "labels": policy()["required_runner_labels"],
            "head_sha": SHA,
            "observed_at": (NOW - timedelta(seconds=30)).isoformat(),
        },
    }
    receipt_payload = {
        "schema_version": 1, "issuer": native.ISSUER,
        "issued_at": (NOW - timedelta(seconds=60)).isoformat(),
        "repo": native.ALLOWED_REPO, "source_sha": SHA,
        "environment": "dev", "profile": "native_runtime",
        "profile_label": "reqsys-dev-native-runtime-v1",
        "runner_instance_id": ID, "physical_host_id": HOST,
        "runner_status": "online", "runner_busy": False,
        "runner_labels": policy()["required_runner_labels"],
        "gates": {k: True for k in REQUIRED_GATES},
        "lease_id": "lease-exclusive-a1b2c3d4", "checkpoint_sha256": "b" * 64,
    }
    receipt = signed(receipt_payload)
    claim = {
        "schema_version": 1, "issuer": native.ISSUER,
        "issued_at": (NOW - timedelta(seconds=20)).isoformat(),
        "source_sha": SHA, "runner_instance_id": ID,
        "bundle_sha256": hashlib.sha256(_canonical_bytes(bundle)).hexdigest(),
        "receipt_sha256": hashlib.sha256(_canonical_bytes(receipt)).hexdigest(),
    }
    return bundle, receipt, signed(claim)


def check(bundle, receipt, attestation, **kwargs):
    return native.verify_gateway_source(
        policy(), bundle, receipt, attestation,
        verifier_key=KEY, expected_sha=SHA,
        expected_runner_instance_id=ID,
        expected_github_run_id=RUN_ID, at=NOW, **kwargs,
    )


def manifest(root):
    return {
        "schema_version": 1, "profile": "native_runtime",
        "environment": "dev", "runner_instance_id": ID,
        "source_sha": SHA, "runtime_root": str(root),
        "runner_labels": policy()["required_runner_labels"],
        "capabilities": policy()["required_tools"],
        "allowed_environments": ["dev"],
        "safeguards": {"hml_enabled": False, "stg_enabled": False,
                       "production_enabled": False, "automatic_retry_enabled": False},
    }


def local(data, root, **extra):
    return native.local_preflight(policy(), data,
                                  expected_sha=SHA, expected_runner_instance_id=ID,
                                  root=root, os_name="nt", architecture="AMD64",
                                  which=lambda k: "found" if k in {"git", "python", "node"} else None,
                                  **extra)


def test_local_positive_never_ready_and_idempotent(tmp_path):
    m = manifest(tmp_path)
    a, b = local(m, tmp_path), local(m, tmp_path)
    assert a == b
    assert a["status"] == "LOCAL_PREFLIGHT_ONLY"
    assert a["ready_for_work"] is False
    assert a["dispatch_allowed"] is False
    assert a["independent_receipt_validated"] is False


@pytest.mark.parametrize("field,value,reason", [
    ("profile", "runtime", "manifest_scope_invalid"),
    ("environment", "prod", "manifest_scope_invalid"),
    ("source_sha", "c"*40, "manifest_sha_mismatch"),
    ("runner_instance_id", "reqsys-pc-another1234", "manifest_identity_mismatch"),
    ("capabilities", ["git", "python", "docker"], "manifest_capability_invalid"),
    ("runner_labels", ["reqsys-dev-runtime-v1"], "manifest_capability_invalid"),
    ("allowed_environments", ["dev", "prod"], "manifest_scope_invalid"),
    ("safeguards", {"production_enabled": True}, "manifest_safeguards_invalid"),
])
def test_local_rejects_changes(tmp_path, field, value, reason):
    m = manifest(tmp_path)
    m[field] = value
    with pytest.raises(NativeAdmissionBlocked, match=reason):
        local(m, tmp_path)


def test_local_rejects_nonwindows_and_bad_arch(tmp_path):
    for os_name, arch in (("posix", "AMD64"), ("nt", "arm64")):
        with pytest.raises(NativeAdmissionBlocked, match="windows_x64_required"):
            native.local_preflight(policy(), manifest(tmp_path),
                expected_sha=SHA, expected_runner_instance_id=ID,
                root=tmp_path, os_name=os_name, architecture=arch,
                which=lambda x: "found")


def test_local_rejects_missing_tool_and_reparse(tmp_path):
    with pytest.raises(NativeAdmissionBlocked, match="native_tool_missing"):
        native.local_preflight(policy(), manifest(tmp_path), expected_sha=SHA,
             expected_runner_instance_id=ID, root=tmp_path, os_name="nt", architecture="AMD64",
             which=lambda x: None)
    linked = tmp_path.parent / (tmp_path.name + "-linked")
    linked.symlink_to(tmp_path, target_is_directory=True)
    m = manifest(linked)
    with pytest.raises(NativeAdmissionBlocked, match="runtime_reparse_refused"):
        local(m, linked)


def test_local_unknown_field_and_root_block(tmp_path):
    m = manifest(tmp_path)
    m["docker_enabled"] = False
    with pytest.raises(NativeAdmissionBlocked, match="manifest_contract_invalid"):
        local(m, tmp_path)
    with pytest.raises(NativeAdmissionBlocked, match="runtime_root_invalid"):
        local(manifest(tmp_path), tmp_path / "missing")


def test_independent_signed_binding_positive_still_not_ready():
    a = fixture()
    result = check(*a)
    assert result["status"] == "INDEPENDENT_GATEWAY_BINDING_VALIDATED"
    assert result["independent_receipt_validated"] is True
    assert result["ready_for_work"] is False
    assert result["dispatch_allowed"] is False
    assert result["continuity_certified"] is False
    assert result == check(*a)


@pytest.mark.parametrize("area,field,value,reason", [
    ("launcher", "result", "NOT_LAUNCHED", "session_launcher_unverified"),
    ("launcher", "state_validated", False, "session_launcher_unverified"),
    ("launcher", "head", "d"*40, "session_launcher_unverified"),
    ("launcher", "profile", "TEST", "session_launcher_unverified"),
    ("launcher", "lease_exclusive", False, "session_launcher_unverified"),
    ("gateway", "result", "error", "gateway_readback_unverified"),
    ("gateway", "gateway_exit_code", 1, "gateway_readback_unverified"),
    ("gateway", "state_changed", True, "gateway_readback_unverified"),
    ("gateway", "session_id", "session-other-other", "gateway_readback_unverified"),
    ("gateway", "command_tag", "arbitrary-command", "gateway_readback_unverified"),
    ("github", "status", "offline", "github_inventory_unverified"),
    ("github", "busy", True, "github_inventory_unverified"),
    ("github", "head_sha", "c"*40, "github_inventory_unverified"),
    ("github", "physical_host_id", "host-different-12345", "github_inventory_unverified"),
    ("github", "labels", ["reqsys-dev-runtime-v1"], "github_inventory_unverified"),
])
def test_bundle_rejects_fake_sources(area, field, value, reason):
    bundle, receipt, attestation = fixture()
    bundle[area][field] = value
    with pytest.raises(NativeAdmissionBlocked, match=reason):
        check(bundle, receipt, attestation)


def test_attestation_digest_detects_tamper_after_signed():
    bundle, receipt, attestation = fixture()
    bundle["gateway"]["correlation_id"] = "another-correlation-valid123"
    with pytest.raises(NativeAdmissionBlocked, match="bundle_digest_mismatch"):
        check(bundle, receipt, attestation)


def test_attestation_signature_detects_fake_issuer():
    bundle, receipt, attestation = fixture()
    attestation["payload"]["issued_at"] = (NOW-timedelta(seconds=10)).isoformat()
    with pytest.raises(NativeAdmissionBlocked, match="attestation_signature_invalid"):
        check(bundle, receipt, attestation)


def test_receipt_digest_detects_tampering():
    bundle, receipt, attestation = fixture()
    receipt["payload"]["checkpoint_sha256"] = "c"*64
    with pytest.raises(NativeAdmissionBlocked, match="receipt_digest_mismatch"):
        check(bundle, receipt, attestation)


def test_expired_inventory_or_attestation_fail_closed():
    bundle, receipt, attestation = fixture()
    bundle["github"]["observed_at"] = (NOW - timedelta(minutes=7)).isoformat()
    with pytest.raises(NativeAdmissionBlocked, match="github_inventory_stale"):
        check(bundle, receipt, attestation)
    bundle, receipt, attestation = fixture()
    attestation["payload"]["issued_at"] = (NOW - timedelta(minutes=7)).isoformat()
    attestation = signed(attestation["payload"])
    with pytest.raises(NativeAdmissionBlocked, match="attestation_time_invalid"):
        check(bundle, receipt, attestation)


def test_run_id_binding_fails_closed():
    bundle, receipt, attestation = fixture()
    with pytest.raises(NativeAdmissionBlocked, match="github_inventory_unverified"):
        native.verify_gateway_source(policy(), bundle, receipt, attestation,
            verifier_key=KEY, expected_sha=SHA,
            expected_runner_instance_id=ID, expected_github_run_id=RUN_ID+1, at=NOW)


def test_no_independent_key_or_hosted_context_blocks(tmp_path, monkeypatch, capsys):
    bundle, receipt, attestation = fixture()
    with pytest.raises(NativeAdmissionBlocked, match="validator_key_missing"):
        native.verify_gateway_source(policy(), bundle, receipt, attestation,
            verifier_key=b"", expected_sha=SHA, expected_runner_instance_id=ID,
            expected_github_run_id=RUN_ID, at=NOW)
    import json as _json
    files = {}
    for name, obj in (("policy", policy()), ("bundle", bundle),
                      ("receipt", receipt), ("attestation", attestation)):
        path = tmp_path / f"{name}.json"
        path.write_text(_json.dumps(obj), encoding="utf-8")
        files[name] = str(path)
    monkeypatch.delenv("RUNNER_ENVIRONMENT", raising=False)
    monkeypatch.setattr(sys, "argv", ["preflight", "--mode", "independent",
        "--policy", files["policy"], "--bundle", files["bundle"],
        "--receipt", files["receipt"], "--attestation", files["attestation"],
        "--expected-sha", SHA, "--runner-instance-id", ID,
        "--github-run-id", str(RUN_ID)])
    assert native.main() == 1
    output = json.loads(capsys.readouterr().out)
    assert output["reason_code"] == "independent_hosted_context_required"
    assert output["ready_for_work"] is False


def test_extra_fields_and_nonallowlisted_command_fail_closed():
    bundle, receipt, attestation = fixture()
    bundle["gateway"]["shell"] = "powershell"
    with pytest.raises(NativeAdmissionBlocked, match="gateway_contract_invalid"):
        check(bundle, receipt, attestation)


def test_action_is_isolated_and_not_executable_workflow():
    txt = (ROOT / ".github/actions/reqsys-native-dev-preflight/action.yml").read_text()
    assert "--mode local" in txt
    assert "REQSYS_NATIVE_VALIDATOR_KEY" not in txt
    assert "--mode independent" not in txt
    executable = txt.split("      run: |", 1)[-1]
    assert "docker" not in executable.casefold()
    assert "--expected-sha" in txt
    assert "GITHUB_SHA" in txt
