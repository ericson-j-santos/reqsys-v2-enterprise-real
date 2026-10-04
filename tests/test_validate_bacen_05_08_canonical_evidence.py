from __future__ import annotations

from pathlib import Path

import yaml

from scripts.validate_bacen_05_08_canonical_evidence import validate

ROOT = Path(__file__).resolve().parents[1]
THIRD = ROOT / "governance/bacen/PROD-THIRD-PARTY-DOCUMENTARY-EVIDENCE.yaml"
EXECUTIVE = ROOT / "governance/bacen/BACEN-08-FORMALIZATION-PACKET.yaml"


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_canonical_evidence_packets_are_fail_closed() -> None:
    result = validate(THIRD, EXECUTIVE)
    assert result["ok"] is True
    assert result["bacen_05_documented_provider_ids"] == ["T01", "T06", "T14"]
    assert result["bacen_05_legal_signoff_complete"] is False
    assert result["bacen_08_formal_designation_complete"] is False
    assert result["bacen_08_annual_report_signoff_complete"] is False
    assert result["control_statuses"] == {"BACEN-05": "partial", "BACEN-08": "partial"}
    assert result["production_touched"] is False
    assert result["status_promotion_allowed"] is False


def test_rejects_untrusted_document_domain(tmp_path: Path) -> None:
    third = yaml.safe_load(THIRD.read_text(encoding="utf-8"))
    third["providers"][0]["official_documents"][0]["source_url"] = "https://example.com/fake-dpa"
    path = _write(tmp_path, "third.yaml", third)
    result = validate(path, EXECUTIVE)
    assert result["ok"] is False
    assert any("expected HTTPS domain" in error for error in result["errors"])


def test_rejects_artificial_legal_approval_without_reference(tmp_path: Path) -> None:
    third = yaml.safe_load(THIRD.read_text(encoding="utf-8"))
    third["providers"][1]["legal_review"]["status"] = "approved"
    path = _write(tmp_path, "third.yaml", third)
    result = validate(path, EXECUTIVE)
    assert result["ok"] is False
    assert any("approved legal review requires signoff_reference" in error for error in result["errors"])


def test_fly_dpa_cannot_be_active_without_customer_signature(tmp_path: Path) -> None:
    third = yaml.safe_load(THIRD.read_text(encoding="utf-8"))
    fly = next(item for item in third["providers"] if item["id"] == "T14")
    dpa = next(doc for doc in fly["official_documents"] if doc["type"] == "data_processing_agreement_request")
    dpa["contract_activation_status"] = "active"
    path = _write(tmp_path, "third.yaml", third)
    result = validate(path, EXECUTIVE)
    assert result["ok"] is False
    assert any("active DPA requires customer_signature_reference" in error for error in result["errors"])


def test_bacen_08_cannot_be_marked_formal_by_automation(tmp_path: Path) -> None:
    executive = yaml.safe_load(EXECUTIVE.read_text(encoding="utf-8"))
    executive["formal_designation"]["status"] = "approved"
    executive["annual_report"]["status"] = "formally_signed"
    path = _write(tmp_path, "executive.yaml", executive)
    result = validate(THIRD, path)
    assert result["ok"] is False
    assert any("formal designation must remain pending human signoff" in error for error in result["errors"])
    assert any("annual report must remain draft pending human signoff" in error for error in result["errors"])
