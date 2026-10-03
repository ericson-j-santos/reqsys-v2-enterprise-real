from __future__ import annotations

import base64
import hashlib
import json

import pytest

from scripts.ingest_bacen_02_mfa_evidence import (
    decode_base64_environment,
    ingest_payload,
)


def _payload(status: str = "validated") -> bytes:
    document = {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "provider": "corporate_idp",
        "environment": "STG",
        "evidence_status": status,
        "collected_at": "2026-07-30T18:00:00Z" if status != "pending_integration" else None,
        "period_start": "2026-07-01" if status != "pending_integration" else None,
        "period_end": "2026-07-30" if status != "pending_integration" else None,
        "mfa_enforced": True if status != "pending_integration" else None,
        "privileged_identities_total": 2 if status != "pending_integration" else 0,
        "privileged_identities_with_mfa": 2 if status != "pending_integration" else 0,
        "evidence_reference": "vault://bacen/mfa/2026-07" if status != "pending_integration" else None,
        "source_system": "identity_provider",
        "production_touched": False,
    }
    return json.dumps(document).encode("utf-8")


def test_accepts_validated_full_coverage_without_persisting_raw_payload() -> None:
    payload = _payload()
    report, accepted = ingest_payload(
        payload,
        hashlib.sha256(payload).hexdigest(),
        require_evidenced=True,
    )

    assert accepted is True
    assert report["mfa_evidenced"] is True
    assert report["ingestion"]["expected_sha256_match"] is True
    assert report["ingestion"]["raw_evidence_persisted"] is False
    assert "evidence_reference" not in report


def test_rejects_hash_mismatch() -> None:
    with pytest.raises(ValueError, match="source_sha256_mismatch"):
        ingest_payload(_payload(), "0" * 64, require_evidenced=True)


def test_pending_contract_is_not_accepted_as_real_ingestion() -> None:
    payload = _payload("pending_integration")
    report, accepted = ingest_payload(
        payload,
        hashlib.sha256(payload).hexdigest(),
        require_evidenced=True,
    )

    assert accepted is False
    assert report["structural_checks_passed"] is True
    assert report["mfa_evidenced"] is False
    assert report["human_review_required"] is True


def test_reads_payload_from_environment_without_logging_value(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload()
    monkeypatch.setenv("BACEN_TEST_MFA", base64.b64encode(payload).decode("ascii"))
    assert decode_base64_environment("BACEN_TEST_MFA") == payload


def test_rejects_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BACEN_TEST_MFA", raising=False)
    with pytest.raises(ValueError, match="não configurado"):
        decode_base64_environment("BACEN_TEST_MFA")
