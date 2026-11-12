"""Controle por fixtures: não é teste de Gateway ou CAS real."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.reqsys_native_external_sources import MTLSReader, read_original_sources
from scripts.validate_reqsys_native_dev_profile import NativeAdmissionBlocked

EVENT = "native-event-123456789012345"
SHA = "a" * 40
HASH = "b" * 64
HOST = "host-physical-12345678"
SESSION = "session-physical-12345"
CORRELATION = "correlation-physical-1234"
LEASE = "lease-physical-1234567"
A = "https://audit.example.org"
C = "https://cas.example.org"


def records():
    return (
        {"schema_version": 1, "source": "trusted-independent-command-gateway-audit-v1",
         "event_id": EVENT, "source_sha": SHA, "session_id": SESSION,
         "correlation_id": CORRELATION, "command_tag": "reqsys-native-dev-readonly-probe",
         "result": "ok", "gateway_exit_code": 0, "state_changed": False},
        {"schema_version": 1, "source": "trusted-independent-cas-readback-v1",
         "event_id": EVENT, "source_sha": SHA, "physical_host_id": HOST,
         "lease_id": LEASE, "checkpoint_sha256": HASH,
         "lease_exclusive": True, "state_validated": True},
    )


def observed(audit=None, cas=None, **changes):
    a, c = records()
    args = dict(audit_origin=A, cas_origin=C,
                audit_get=lambda _: a if audit is None else audit,
                cas_get=lambda _: c if cas is None else cas,
                event_id=EVENT, source_sha=SHA, physical_host_id=HOST,
                session_id=SESSION, correlation_id=CORRELATION,
                lease_id=LEASE, checkpoint_sha256=HASH)
    args.update(changes)
    return read_original_sources(**args)


def test_positive_and_replay_do_not_claim_readiness():
    first = observed()
    assert first == observed()
    assert first["status"] == "EXTERNAL_READBACK_ONLY"
    for flag in ("ready_for_work", "dispatch_allowed", "continuity_certified"):
        assert first[flag] is False


@pytest.mark.parametrize("bad", [
    "http://audit.example.org", "https://localhost", "https://127.0.0.1", "https://192.168.0.1", "https://8.8.8.8",
    "https://audit.example.org/path", "https://audit.example.org?query=1",
    "https://audit.example.org:443", "https://user:pass@audit.example.org",
    "https://audit.example.org/", "",
])
def test_insecure_origins_rejected(bad):
    with pytest.raises(NativeAdmissionBlocked):
        observed(audit_origin=bad)


def test_two_authorities_are_required():
    with pytest.raises(NativeAdmissionBlocked, match="external_origins_not_independent"):
        observed(cas_origin=A)


@pytest.mark.parametrize("field,value", [
    ("event_id", "native-wrong-1234567890123"),
    ("session_id", "other-session-12345678"),
    ("correlation_id", "different-correlation-1234"),
    ("gateway_exit_code", 1),
    ("state_changed", True),
    ("source_sha", "c" * 40),
])
def test_gateway_original_evidence_cannot_be_replaced(field, value):
    a, _ = records()
    a[field] = value
    with pytest.raises(NativeAdmissionBlocked):
        observed(audit=a)


@pytest.mark.parametrize("field,value", [
    ("physical_host_id", "host-otherhost-12345"),
    ("lease_id", "other-lease-12345678"),
    ("checkpoint_sha256", "c" * 64),
    ("lease_exclusive", False),
    ("state_validated", False),
    ("source_sha", "c" * 40),
])
def test_checkpoint_and_lease_tampering_fails(field, value):
    _, c = records()
    c[field] = value
    with pytest.raises(NativeAdmissionBlocked):
        observed(cas=c)


def test_missing_external_source_fails_closed():
    def fail(_):
        raise OSError("network unavailable")
    with pytest.raises(NativeAdmissionBlocked, match="external_source_unavailable"):
        observed(audit_get=fail)


def test_no_client_credentials_means_no_connection(tmp_path: Path):
    with pytest.raises(NativeAdmissionBlocked, match="external_tls_unprovisioned"):
        MTLSReader(origin=A, ca=tmp_path / "ca.pem",
                   client_cert=tmp_path / "cert.pem", client_key=tmp_path / "key.pem")


def test_of_test_detects_forged_original_event():
    a, _ = records()
    a["event_id"] = "native-forged-1234567890123"
    with pytest.raises(NativeAdmissionBlocked):
        observed(audit=a)
