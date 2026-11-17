"""Contrato negativo e positivo do pré-admissor; nenhum host ou serviço é acessado."""
import hashlib
import hmac
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_reqsys_native_dev_profile import (  # noqa: E402
    NativeAdmissionBlocked, validate_contract, verify_independent_receipt,
    _canonical_bytes, REQUIRED_LABELS, REQUIRED_GATES,
)

KEY = b"test-key-not-for-production-0000000000000000"
SHA = "a" * 40
HOST = "reqsys-pc-a1b2c3d4"
NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


def policy():
    return json.loads((ROOT / "config/reqsys-native-dev-profile.json").read_text())


def signed(payload, key=KEY):
    return {"payload": payload,
            "signature": hmac.new(key, _canonical_bytes(payload), hashlib.sha256).hexdigest()}


def valid_receipt():
    p = {
        "schema_version": 1,
        "issuer": "reqsys-governed-independent-validator-v1",
        "issued_at": (NOW-timedelta(seconds=90)).isoformat(),
        "repo": "ericson-j-santos/reqsys-v2-enterprise-real",
        "source_sha": SHA,
        "environment": "dev",
        "profile": "native_runtime", "profile_label": "reqsys-dev-native-runtime-v1",
        "runner_instance_id": HOST, "physical_host_id": "host-physical-a1b2c3d4",
        "runner_status": "online", "runner_busy": False,
        "runner_labels": list(REQUIRED_LABELS),
        "gates": {v: True for v in REQUIRED_GATES},
        "lease_id": "lease-exclusive-a1b2c3d4", "checkpoint_sha256": "b" * 64,
    }
    return signed(p)


def check(rec, **kwargs):
    return verify_independent_receipt(policy(), rec, verifier_key=KEY,
                                      expected_sha=SHA, expected_runner_instance_id=HOST,
                                      at=NOW, **kwargs)


def test_static_profile_valid_but_not_ready():
    r = validate_contract(policy())
    assert r["status"] == "policy_validated"
    assert r["ready_for_work"] is False
    assert r["dispatch_allowed"] is False


def test_signed_independent_receipt_only_preflights_never_dispatches():
    result = check(valid_receipt())
    assert result["ready_for_work"] is True
    assert result["continuity_certified"] is False
    assert result["dispatch_allowed"] is False


def test_signature_replay_deterministic_and_idempotent():
    a = check(valid_receipt())
    b = check(valid_receipt())
    assert a == b


@pytest.mark.parametrize("field,value,reason", [
    ("environment", "prod", "receipt_scope_invalid"),
    ("source_sha", "c" * 40, "receipt_sha_mismatch"),
    ("profile", "runtime", "receipt_profile_invalid"),
    ("profile_label", "reqsys-dev-runtime-v1", "receipt_profile_invalid"),
    ("runner_instance_id", "reqsys-pc-other1234", "runner_identity_mismatch"),
    ("runner_status", "offline", "runner_not_idle"),
    ("runner_busy", True, "runner_not_idle"),
    ("lease_id", "", "lease_unavailable"),
    ("checkpoint_sha256", "invalid", "checkpoint_invalid"),
])
def test_reject_negative_receipts(field, value, reason):
    r = valid_receipt()
    r["payload"][field] = value
    with pytest.raises(NativeAdmissionBlocked, match=reason):
        check(signed(r["payload"]))


@pytest.mark.parametrize("gate", REQUIRED_GATES)
def test_each_gate_fail_closed(gate):
    r = valid_receipt()["payload"]
    r["gates"][gate] = False
    with pytest.raises(NativeAdmissionBlocked, match="required_gate_failed"):
        check(signed(r))


def test_tampered_receipt_detected():
    r = valid_receipt()
    r["payload"]["gates"]["gateway_validated"] = False
    with pytest.raises(NativeAdmissionBlocked, match="receipt_signature_invalid"):
        check(r)


def test_untrusted_receipt_or_missing_key_blocked():
    with pytest.raises(NativeAdmissionBlocked, match="verifier_key_unavailable"):
        verify_independent_receipt(policy(), valid_receipt(), verifier_key=b"",
                                   expected_sha=SHA, expected_runner_instance_id=HOST, at=NOW)
    with pytest.raises(NativeAdmissionBlocked, match="receipt_signature_invalid"):
        verify_independent_receipt(policy(), valid_receipt(), verifier_key=b"other-key-also-long-0000000000000000000",
                                   expected_sha=SHA, expected_runner_instance_id=HOST, at=NOW)


def test_expired_and_future_receipts_blocked():
    for delta in (timedelta(minutes=6), timedelta(seconds=-1)):
        payload = valid_receipt()["payload"]
        payload["issued_at"] = (NOW-delta).isoformat()
        with pytest.raises(NativeAdmissionBlocked, match="receipt_expired_or_future"):
            check(signed(payload))


def test_policy_cannot_confuse_legacy_docker_profiles():
    for field, value in (("profile", "runtime"), ("profile_label", "reqsys-dev-runtime-v1"),
                         ("required_tools", ["git", "python", "docker"]),
                         ("dispatch_allowed", True), ("managed_labels_may_change", True)):
        p = policy()
        p[field] = value
        with pytest.raises(NativeAdmissionBlocked, match="native_policy_contract_invalid"):
            validate_contract(p)


def test_unknown_fields_and_noncanonical_labels_blocked():
    p = valid_receipt()["payload"]
    p["unexpected_capability"] = "docker"
    with pytest.raises(NativeAdmissionBlocked, match="receipt_fields_invalid"):
        check(signed(p))
    p = valid_receipt()["payload"]
    p["runner_labels"] = list(REQUIRED_LABELS) + ["reqsys-dev-runtime-v1"]
    with pytest.raises(NativeAdmissionBlocked, match="runner_labels_invalid"):
        check(signed(p))
