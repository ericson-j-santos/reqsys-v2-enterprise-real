"""Pure, cross-platform tests for the NOTERI -> desktop bundle format."""

from __future__ import annotations

import base64
import os
import struct
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import noteri_desktop_bundle_transport as transport


@pytest.fixture(scope="module")
def recipient_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=3072)


@pytest.fixture
def plaintext(tmp_path):
    path = tmp_path / "source.bin"
    path.write_bytes((b"reqsys-streaming-migration\x00" * 200_000) + b"tail")
    return path


def _sealed(tmp_path, plaintext, recipient_key, *, now=1_000, ttl=600):
    envelope = tmp_path / "bundle.rsb"
    report = transport.seal_file(
        plaintext,
        envelope,
        recipient_key.public_key(),
        now=now,
        ttl_seconds=ttl,
    )
    return envelope, report


def _receive(envelope, restored, recipient_key, sealed, *, now=1_100):
    return transport.receive_file(
        envelope,
        restored,
        recipient_key,
        expected_envelope_sha256=sealed["envelope_sha256"],
        expected_plaintext_sha256=sealed["plaintext_sha256"],
        expected_plaintext_bytes=sealed["plaintext_bytes"],
        now=now,
    )


def _ciphertext_offset(envelope: bytes) -> int:
    header_size = struct.unpack(
        ">I", envelope[len(transport.MAGIC) : len(transport.MAGIC) + 4]
    )[0]
    return (
        len(transport.MAGIC)
        + 4
        + header_size
        + 2
        + transport.WRAPPED_KEY_BYTES
        + transport.NONCE_BYTES
    )


def test_streaming_round_trip_and_bound_header(tmp_path, plaintext, recipient_key):
    envelope, sealed = _sealed(tmp_path, plaintext, recipient_key)
    restored = tmp_path / "restored.bin"

    opened = _receive(envelope, restored, recipient_key, sealed)

    assert restored.read_bytes() == plaintext.read_bytes()
    assert opened["plaintext_sha256"] == sealed["plaintext_sha256"]
    assert opened["plaintext_bytes"] == plaintext.stat().st_size
    assert opened["recipient_sha256"] == transport.recipient_fingerprint(
        recipient_key.public_key()
    )
    assert envelope.read_bytes().startswith(transport.MAGIC)


def test_ciphertext_tamper_is_rejected_without_publishing(
    tmp_path, plaintext, recipient_key
):
    envelope, sealed = _sealed(tmp_path, plaintext, recipient_key)
    encoded = bytearray(envelope.read_bytes())
    encoded[_ciphertext_offset(encoded) + 17] ^= 0x80
    envelope.write_bytes(encoded)
    # Supplying the modified artifact digest reaches the GCM tag check.  In
    # normal operation the independently pinned original digest rejects first.
    sealed["envelope_sha256"] = transport.sha256_bytes(encoded)
    restored = tmp_path / "tampered-output.bin"

    with pytest.raises(
        transport.BundleTransportError, match="envelope_authentication_failed"
    ):
        _receive(envelope, restored, recipient_key, sealed)

    assert not restored.exists()


def test_wrong_key_is_rejected_by_recipient_fingerprint(
    tmp_path, plaintext, recipient_key
):
    envelope, sealed = _sealed(tmp_path, plaintext, recipient_key)
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    restored = tmp_path / "wrong-key-output.bin"

    with pytest.raises(
        transport.BundleTransportError, match="recipient_fingerprint_mismatch"
    ):
        _receive(envelope, restored, wrong_key, sealed)

    assert not restored.exists()


def test_expired_envelope_is_rejected(tmp_path, plaintext, recipient_key):
    envelope, sealed = _sealed(tmp_path, plaintext, recipient_key, now=1_000, ttl=60)
    restored = tmp_path / "expired-output.bin"

    with pytest.raises(
        transport.BundleTransportError, match="envelope_expired_or_future"
    ):
        _receive(envelope, restored, recipient_key, sealed, now=1_060)

    assert not restored.exists()


def test_truncated_envelope_is_rejected(tmp_path, plaintext, recipient_key):
    envelope, sealed = _sealed(tmp_path, plaintext, recipient_key)
    envelope.write_bytes(envelope.read_bytes()[:-7])
    sealed["envelope_sha256"] = transport.sha256_bytes(envelope.read_bytes())
    restored = tmp_path / "truncated-output.bin"

    with pytest.raises(transport.BundleTransportError, match="envelope_truncated"):
        _receive(envelope, restored, recipient_key, sealed)

    assert not restored.exists()


def test_existing_destination_is_never_overwritten(tmp_path, plaintext, recipient_key):
    envelope, sealed = _sealed(tmp_path, plaintext, recipient_key)
    restored = tmp_path / "existing.bin"
    restored.write_bytes(b"keep-me")

    with pytest.raises(
        transport.BundleTransportError, match="destination_already_exists"
    ):
        _receive(envelope, restored, recipient_key, sealed)

    assert restored.read_bytes() == b"keep-me"


def test_recipient_config_accepts_existing_identity_schema(recipient_key):
    der = transport.public_der(recipient_key.public_key())
    fingerprint = transport.sha256_bytes(der)
    config = transport.canonical(
        {
            "schema": transport.LEGACY_RECIPIENT_SCHEMA,
            "target_host": transport.TARGET_HOST,
            "public_key_der_b64": base64.b64encode(der).decode("ascii"),
            "recipient_sha256": fingerprint,
        }
    )

    loaded = transport.load_recipient(config, fingerprint)

    assert transport.public_der(loaded) == der


def test_recipient_public_key_accepts_pem_when_pinned(recipient_key):
    public = recipient_key.public_key()
    pem = public.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = transport.recipient_fingerprint(public)

    loaded = transport.load_recipient(pem, fingerprint)

    assert transport.public_der(loaded) == transport.public_der(public)


def test_artifact_digest_pin_rejects_substitution(tmp_path, plaintext, recipient_key):
    envelope, sealed = _sealed(tmp_path, plaintext, recipient_key)
    encoded = bytearray(envelope.read_bytes())
    encoded[_ciphertext_offset(encoded) + 3] ^= 0x01
    envelope.write_bytes(encoded)
    restored = tmp_path / "substituted-output.bin"

    with pytest.raises(
        transport.BundleTransportError, match="artifact_digest_mismatch"
    ):
        _receive(envelope, restored, recipient_key, sealed)

    assert not restored.exists()


def test_single_invocation_limit_matches_nist_gcm_bound():
    assert transport.MAX_PLAINTEXT_BYTES == (2**39 - 256) // 8


def test_expected_plaintext_manifest_is_required(tmp_path, plaintext, recipient_key):
    envelope, sealed = _sealed(tmp_path, plaintext, recipient_key)
    restored = tmp_path / "manifest-mismatch.bin"

    with pytest.raises(
        transport.BundleTransportError, match="expected_plaintext_mismatch"
    ):
        transport.receive_file(
            envelope,
            restored,
            recipient_key,
            expected_envelope_sha256=sealed["envelope_sha256"],
            expected_plaintext_sha256="0" * 64,
            expected_plaintext_bytes=sealed["plaintext_bytes"],
            now=1_100,
        )

    assert not restored.exists()


def test_legacy_hardening_failure_cannot_publish_destination(
    tmp_path, plaintext, recipient_key
):
    destination = tmp_path / "must-not-publish.rsb"

    class LegacyTransportError(RuntimeError):
        pass

    def fail_hardening(_path):
        raise LegacyTransportError("simulated legacy ACL failure")

    with pytest.raises(LegacyTransportError):
        transport.seal_file(
            plaintext,
            destination,
            recipient_key.public_key(),
            now=1_000,
            ttl_seconds=600,
            harden_file=fail_hardening,
        )

    assert not destination.exists()
    assert not list(tmp_path.glob(".*.partial"))


def test_hard_link_source_is_rejected(tmp_path, plaintext, recipient_key):
    linked = tmp_path / "linked-source.bin"
    try:
        os.link(plaintext, linked)
    except OSError:
        pytest.skip("filesystem does not support hard links")

    with pytest.raises(
        transport.BundleTransportError, match="source_regular_file_required"
    ):
        transport.seal_file(
            linked,
            tmp_path / "hard-link-output.rsb",
            recipient_key.public_key(),
            now=1_000,
            ttl_seconds=600,
        )


def test_private_temp_is_cleaned_if_chmod_fails(tmp_path, monkeypatch):
    def fail_chmod(_path, _mode):
        raise PermissionError("simulated")

    monkeypatch.setattr(transport.os, "chmod", fail_chmod)

    with pytest.raises(
        transport.BundleTransportError, match="private_temporary_file_failed"
    ):
        transport._new_private_temp(tmp_path / "destination.bin")

    assert not list(tmp_path.iterdir())
