from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from scripts.ingest_bacen_05_dpa_references import ingest_payload


def _register(tmp_path: Path) -> Path:
    path = tmp_path / "register.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "control_id": "BACEN-05",
                "providers": [
                    {"id": "BACEN-05-T01", "provider": "Provider One"},
                    {"id": "BACEN-05-T02", "provider": "Provider Two"},
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _payload(vendor_id: str = "BACEN-05-T01", status: str = "validated") -> bytes:
    approved = status == "validated"
    contract = {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "mode": "advisory",
        "privacy": {
            "store_document_content": False,
            "allowed_reference_schemes": ["https", "sharepoint", "vault"],
        },
        "records": [
            {
                "vendor_id": vendor_id,
                "evidence_status": status,
                "document_reference": "vault://bacen/dpa/provider-one",
                "document_sha256": "a" * 64,
                "effective_at": "2026-01-01",
                "expires_at": "2027-01-01",
                "jurisdiction": "BR",
                "legal_approval_status": "approved" if approved else "pending",
                "legal_approval_reference": "LEGAL-2026-001" if approved else None,
            }
        ],
    }
    return yaml.safe_dump(contract, sort_keys=False).encode("utf-8")


def test_accepts_validated_reference_for_registered_vendor(tmp_path: Path) -> None:
    payload = _payload()
    report, accepted = ingest_payload(
        payload,
        hashlib.sha256(payload).hexdigest(),
        register_path=_register(tmp_path),
        minimum_validated_records=1,
    )

    assert accepted is True
    assert report["summary"]["validated_records"] == 1
    assert report["registry_validation"]["unknown_vendor_ids"] == []
    assert report["ingestion"]["raw_evidence_persisted"] is False
    assert "records" not in report


def test_rejects_unknown_vendor(tmp_path: Path) -> None:
    payload = _payload("BACEN-05-T99")
    report, accepted = ingest_payload(
        payload,
        hashlib.sha256(payload).hexdigest(),
        register_path=_register(tmp_path),
        minimum_validated_records=1,
    )

    assert accepted is False
    assert report["registry_validation"]["unknown_vendor_ids"] == ["BACEN-05-T99"]


def test_rejects_payload_without_validated_record(tmp_path: Path) -> None:
    payload = _payload(status="pending")
    report, accepted = ingest_payload(
        payload,
        hashlib.sha256(payload).hexdigest(),
        register_path=_register(tmp_path),
        minimum_validated_records=1,
    )

    assert accepted is False
    assert report["summary"]["validated_records"] == 0
    assert report["human_review_required"] is True


def test_rejects_hash_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source_sha256_mismatch"):
        ingest_payload(
            _payload(),
            "0" * 64,
            register_path=_register(tmp_path),
            minimum_validated_records=1,
        )


def test_rejects_duplicate_vendor_records(tmp_path: Path) -> None:
    contract = yaml.safe_load(_payload().decode("utf-8"))
    contract["records"].append(dict(contract["records"][0]))
    payload = yaml.safe_dump(contract, sort_keys=False).encode("utf-8")

    report, accepted = ingest_payload(
        payload,
        hashlib.sha256(payload).hexdigest(),
        register_path=_register(tmp_path),
        minimum_validated_records=1,
    )

    assert accepted is False
    assert report["registry_validation"]["duplicate_vendor_ids"] == ["BACEN-05-T01"]
