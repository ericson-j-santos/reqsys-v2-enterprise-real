from pathlib import Path

import yaml

from scripts.validate_bacen_dpa_evidence_contract import build_report


def write_contract(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "contract.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "privacy": {"allowed_reference_schemes": ["https", "vault"]},
                "records": records,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def valid_record() -> dict:
    return {
        "vendor_id": "BACEN-05-T01",
        "evidence_status": "validated",
        "document_reference": "vault://legal/dpa/vendor-01",
        "document_sha256": "a" * 64,
        "effective_at": "2026-01-01",
        "expires_at": "2027-01-01",
        "jurisdiction": "BR",
        "legal_approval_status": "approved",
        "legal_approval_reference": "LEGAL-2026-001",
    }


def test_empty_contract_is_valid_and_advisory(tmp_path: Path) -> None:
    report = build_report(write_contract(tmp_path, []))
    assert report["result"] == "valid"
    assert report["summary"]["total_records"] == 0
    assert report["production_touched"] is False


def test_valid_reference_is_accepted_without_document_content(tmp_path: Path) -> None:
    report = build_report(write_contract(tmp_path, [valid_record()]))
    assert report["result"] == "valid"
    assert report["summary"]["validated_records"] == 1


def test_document_content_is_rejected(tmp_path: Path) -> None:
    record = valid_record()
    record["document_content"] = "conteúdo proibido"
    report = build_report(write_contract(tmp_path, [record]))
    assert report["result"] == "invalid"
    assert report["automatic_blocking"] is True


def test_validated_evidence_requires_legal_approval(tmp_path: Path) -> None:
    record = valid_record()
    record["legal_approval_status"] = "pending"
    report = build_report(write_contract(tmp_path, [record]))
    assert report["result"] == "invalid"
