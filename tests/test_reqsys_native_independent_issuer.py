"""Emissão sintética NÃO comprova nenhum host, Gateway ou credencial real."""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import reqsys_native_independent_issuer as issuer  # noqa: E402
from scripts.validate_reqsys_native_dev_profile import (  # noqa: E402
    NativeAdmissionBlocked, REQUIRED_GATES, _canonical_bytes,
)

NOW = datetime(2026, 11, 11, 16, 0, tzinfo=timezone.utc)
SHA = "a" * 40
PC = "reqsys-pc-a1b2c3d4"
HOST = "host-physical-a1b2c3d4"
WITNESS_PRIVATE = Ed25519PrivateKey.from_private_bytes(b"\x01" * 32)
WITNESS_PUBLIC = WITNESS_PRIVATE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
ISSUER_KEY = b"fixture-issuer-secret-never-use-in-prod-2"
TOKEN = "github-fake-token-only-for-tests-000000"
LABELS = ["self-hosted", "Windows", "X64", "reqsys-dev", "reqsys-dev-base-v1",
          "reqsys-dev-native-runtime-v1"]
CTX = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
       "GITHUB_REPOSITORY": issuer.ALLOWED_REPO, "GITHUB_SHA": SHA}


def policy():
    return json.loads((ROOT / "config/reqsys-native-dev-profile.json").read_text())


def digest(data):
    return hashlib.sha256(_canonical_bytes(data)).hexdigest()


def signed(data, key=WITNESS_PRIVATE):
    return {"payload": data, "signature": key.sign(_canonical_bytes(data)).hex()}


def fixtures():
    launcher = {
        "result": "SESSION_LAUNCH_OK", "state_validated": True,
        "head": SHA, "session_id": "session-unique-a1b2c3d4",
        "host": HOST, "profile": "NORMAL", "worktree_exclusive": True,
        "lease_exclusive": True,
    }
    gateway = {
        "result": "ok", "gateway_exit_code": 0, "state_changed": False,
        "head": SHA, "session_id": launcher["session_id"],
        "command_tag": issuer.COMMAND_TAG,
        "correlation_id": "correlation-native-test-12345",
    }
    audit = {
        "schema_version": 1, "source": issuer.WITNESS_SOURCE,
        "event_id": "native-event-1234567890", "source_sha": SHA,
        "session_id": launcher["session_id"],
        "correlation_id": gateway["correlation_id"],
        "command_tag": issuer.COMMAND_TAG, "result": "ok",
        "gateway_exit_code": 0, "state_changed": False,
    }
    checkpoint = {
        "schema_version": 1, "source": "trusted-independent-cas-readback-v1",
        "event_id": audit["event_id"], "source_sha": SHA,
        "physical_host_id": HOST, "lease_id": "lease-exclusive-a1b2c3d4",
        "checkpoint_sha256": "b"*64,
        "lease_exclusive": True, "state_validated": True,
    }
    payload = {
        "schema_version": 1, "issuer": issuer.WITNESS_ISSUER,
        "source": issuer.WITNESS_SOURCE,
        "issued_at": (NOW-timedelta(seconds=40)).isoformat(),
        "event_id": audit["event_id"], "repo": issuer.ALLOWED_REPO,
        "source_sha": SHA, "run_id": 123, "job_id": 456, "runner_id": 789,
        "runner_instance_id": PC, "physical_host_id": HOST,
        "session_id": launcher["session_id"],
        "correlation_id": gateway["correlation_id"],
        "lease_id": checkpoint["lease_id"],
        "checkpoint_sha256": "b"*64,
        "gates": {k: True for k in REQUIRED_GATES},
        "launcher_sha256": digest(launcher),
        "gateway_audit_sha256": digest(audit),
        "checkpoint_readback_sha256": digest(checkpoint),
    }
    return launcher, gateway, audit, checkpoint, signed(payload)


def responses():
    return {
        "/actions/runs/123": {"id": 123, "head_sha": SHA,
                              "repository": {"full_name": issuer.ALLOWED_REPO}},
        "/actions/jobs/456": {"id": 456, "run_id": 123,
                              "runner_id": 789, "runner_name": "runner-example",
                              "head_sha": SHA, "labels": LABELS},
        "/actions/runners/789": {"id": 789, "status": "online", "busy": False,
                                 "name": "runner-example",
                                 "labels": [{"name": x} for x in LABELS]},
    }


def attempt(*, changes=None, api=None, context=None, witness_key=WITNESS_PUBLIC,
            issuer_key=ISSUER_KEY, at=NOW):
    launcher, gateway, audit, checkpoint, witness = fixtures()
    x = {"launcher": launcher, "gateway": gateway, "audit": audit,
         "checkpoint": checkpoint, "witness": witness}
    if changes:
        changes(x)
    calls = []
    r = api or responses()

    def fetch(path, *, token):
        calls.append((path, token))
        return r[path]

    result = issuer.issue_independent_receipt(
        policy(), x["launcher"], x["gateway"], x["audit"], x["checkpoint"],
        x["witness"], witness_verifier_key=witness_key,
        issuer_signing_key=issuer_key, github_read_token=TOKEN,
        expected_sha=SHA, expected_runner_instance_id=PC,
        expected_run_id=123, expected_job_id=456, expected_runner_id=789,
        execution_context=CTX if context is None else context, fetch=fetch, at=at,
    )
    return result, calls


def resign(x):
    x["witness"] = signed(x["witness"]["payload"])


def test_verified_external_witness_and_official_github_readback():
    result, calls = attempt()
    assert result["status"] == "INDEPENDENT_RECEIPT_EMITTED"
    assert result["verification"]["status"] == "INDEPENDENT_GATEWAY_BINDING_VALIDATED"
    assert [x[0] for x in calls] == ["/actions/runs/123", "/actions/jobs/456",
                                     "/actions/runners/789"]
    assert result["ready_for_work"] is False
    assert result["dispatch_allowed"] is False
    assert result["continuity_certified"] is False
    assert all(z not in json.dumps(result) for z in (TOKEN, WITNESS_PUBLIC.hex(), ISSUER_KEY.decode()))


def test_replay_is_deterministic_and_never_dispatches():
    first, _ = attempt()
    second, _ = attempt()
    assert _canonical_bytes(first) == _canonical_bytes(second)


@pytest.mark.parametrize("change,expected", [
    (lambda x: x["witness"]["payload"].update({"source_sha": "c"*40}),
     "witness_signature_invalid"),
    (lambda x: x["launcher"].update({"head": "c"*40}),
     "launcher_origin_mismatch"),
    (lambda x: x["gateway"].update({"state_changed": True}),
     "gateway_transcript_mismatch"),
    (lambda x: x["audit"].update({"source": "self-reported"}),
     "gateway_audit_origin_mismatch"),
    (lambda x: x["checkpoint"].update({"lease_exclusive": False}),
     "checkpoint_source_mismatch"),
    (lambda x: x["witness"].update({"signature": "0"*128}),
     "witness_signature_invalid"),
    (lambda x: x["witness"]["payload"]["gates"].update({"cost_zero_confirmed": False}),
     "witness_signature_invalid"),
])
def test_tampering_without_authority_is_blocked(change, expected):
    with pytest.raises(NativeAdmissionBlocked, match=expected):
        attempt(changes=change)


@pytest.mark.parametrize("field,value,reason", [
    ("gates", {k: (k != "cost_zero_confirmed") for k in REQUIRED_GATES},
     "witness_gates_not_proven"),
    ("source", "self-reported-runner-data", "witness_issuer_invalid"),
    ("physical_host_id", "host-fake-host-12345", "independent_checkpoint_invalid"),
    ("run_id", 999, "witness_target_mismatch"),
    ("lease_id", "lease-different-12345", "independent_checkpoint_invalid"),
])
def test_even_signed_but_invalid_trust_metadata_is_blocked(field,value,reason):
    def changed(x):
        x["witness"]["payload"][field] = value
        resign(x)
    with pytest.raises(NativeAdmissionBlocked, match=reason):
        attempt(changes=changed)


def test_stale_witness_rejected():
    def changed(x):
        x["witness"]["payload"]["issued_at"] = (NOW-timedelta(seconds=301)).isoformat()
        resign(x)
    with pytest.raises(NativeAdmissionBlocked, match="witness_stale_or_future"):
        attempt(changes=changed)


@pytest.mark.parametrize("field,value", [
    ("GITHUB_ACTIONS", "false"), ("RUNNER_ENVIRONMENT", "self-hosted"),
    ("GITHUB_REPOSITORY", "ericson-j-santos/other"), ("GITHUB_SHA", "b"*40),
])
def test_other_context_cannot_issue(field,value):
    ctx = dict(CTX)
    ctx[field] = value
    with pytest.raises(NativeAdmissionBlocked, match="independent_execution_context_required"):
        attempt(context=ctx)


def test_keys_must_exist_be_distinct_and_outside_host():
    for key1, key2 in ((b"", ISSUER_KEY), (WITNESS_PUBLIC, b""),
                       (ISSUER_KEY, ISSUER_KEY)):
        with pytest.raises(NativeAdmissionBlocked, match="independent_key_custody_invalid"):
            attempt(witness_key=key1, issuer_key=key2)


def test_self_signed_host_cannot_pose_as_independent_witness():
    def changed(x):
        x["witness"] = signed(
            x["witness"]["payload"], Ed25519PrivateKey.from_private_bytes(b"\x02" * 32))
    with pytest.raises(NativeAdmissionBlocked, match="witness_signature_invalid"):
        attempt(changes=changed)


def test_github_official_readback_rejects_wrong_runner_and_sha():
    for name,field,value in (("/actions/runners/789", "status", "offline"),
                             ("/actions/jobs/456", "head_sha", "b"*40),
                             ("/actions/jobs/456", "runner_id", 999)):
        data = responses()
        data[name][field] = value
        with pytest.raises(NativeAdmissionBlocked, match="github_.*"):
            attempt(api=data)


def test_absent_trust_proof_stops_before_github_query():
    calls = []
    def fetch(*args, **kwargs):
        calls.append((args,kwargs))
        pytest.fail("untrusted evidence must not trigger GitHub calls")
    # Synthetic payload with unknown witness key cannot be accepted even with an available API.
    args = fixtures()
    with pytest.raises(NativeAdmissionBlocked, match="witness_signature_invalid"):
        issuer.issue_independent_receipt(
            policy(), *args, witness_verifier_key=b"x"*32,
            issuer_signing_key=ISSUER_KEY, github_read_token=TOKEN,
            expected_sha=SHA, expected_runner_instance_id=PC,
            expected_run_id=123, expected_job_id=456, expected_runner_id=789,
            execution_context=CTX, fetch=fetch, at=NOW)
    assert calls == []



def test_public_key_only_verifies_ed25519_without_signing_capability():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    witness = fixtures()[-1]
    Ed25519PublicKey.from_public_bytes(WITNESS_PUBLIC).verify(
        bytes.fromhex(witness["signature"]), _canonical_bytes(witness["payload"]))
    wrong = Ed25519PrivateKey.from_private_bytes(b"\x03" * 32)
    public = wrong.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    with pytest.raises(NativeAdmissionBlocked, match="witness_signature_invalid"):
        attempt(witness_key=public)


def test_legacy_hmac_and_bad_public_key_fail_closed():
    for key in (b"", b"x" * 31, b"x" * 33):
        with pytest.raises(NativeAdmissionBlocked, match="independent_key_custody_invalid"):
            attempt(witness_key=key)
    def old_symmetric_witness(x):
        payload = x["witness"]["payload"]
        x["witness"] = {"payload": payload, "signature": hmac.new(
            ISSUER_KEY, _canonical_bytes(payload), hashlib.sha256).hexdigest()}
    with pytest.raises(NativeAdmissionBlocked, match="witness_signature_format_invalid"):
        attempt(changes=old_symmetric_witness)


def test_cli_missing_keys_does_not_write_receipt_or_contact_network(tmp_path,monkeypatch,capsys):
    p=tmp_path/"policy.json"
    p.write_text(json.dumps(policy()),encoding="utf-8")
    launcher,gateway,audit,checkpoint,witness=fixtures()
    e=tmp_path/"evidence.json"
    e.write_text(json.dumps({"launcher":launcher,"gateway":gateway,
                             "gateway_audit":audit,"checkpoint_readback":checkpoint,
                             "witness":witness}),encoding="utf-8")
    out=tmp_path/"receipt.json"
    for key in ("REQSYS_NATIVE_GATEWAY_WITNESS_PUBLIC_KEY","REQSYS_NATIVE_VALIDATOR_KEY",
                "REQSYS_NATIVE_GITHUB_READ_TOKEN"):
        monkeypatch.delenv(key,raising=False)
    for key,value in CTX.items():
        monkeypatch.setenv(key,value)
    argv=["--policy",str(p),"--evidence",str(e),"--expected-sha",SHA,
          "--runner-instance-id",PC,"--run-id","123","--job-id","456",
          "--runner-id","789","--output",str(out)]
    assert issuer.main(argv)==1
    response=json.loads(capsys.readouterr().out)
    assert response["status"]=="BLOCKED_INDEPENDENT_ISSUER"
    assert response["reason_code"]=="independent_key_custody_invalid"
    assert not out.exists()


def test_cli_rejects_self_report_without_signed_witness(tmp_path,monkeypatch,capsys):
    p=tmp_path/"policy.json"
    p.write_text(json.dumps(policy()),encoding="utf-8")
    launcher,gateway,audit,checkpoint,_=fixtures()
    e=tmp_path/"evidence.json"
    e.write_text(json.dumps({"launcher":launcher,"gateway":gateway,
                             "gateway_audit":audit,"checkpoint_readback":checkpoint,
                             "witness":{"self_reported":True}}),encoding="utf-8")
    out=tmp_path/"receipt.json"
    for key,value in {"REQSYS_NATIVE_GATEWAY_WITNESS_PUBLIC_KEY":WITNESS_PUBLIC.hex(),
                      "REQSYS_NATIVE_VALIDATOR_KEY":ISSUER_KEY.decode(),
                      "REQSYS_NATIVE_GITHUB_READ_TOKEN":TOKEN, **CTX}.items():
        monkeypatch.setenv(key,value)
    argv=["--policy",str(p),"--evidence",str(e),"--expected-sha",SHA,
          "--runner-instance-id",PC,"--run-id","123","--job-id","456",
          "--runner-id","789","--output",str(out)]
    assert issuer.main(argv)==1
    response=json.loads(capsys.readouterr().out)
    assert response["reason_code"]=="witness_envelope_invalid"
    assert not out.exists()
    assert TOKEN not in json.dumps(response)
