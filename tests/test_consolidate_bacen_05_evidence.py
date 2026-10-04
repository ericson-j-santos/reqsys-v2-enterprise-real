import json
from pathlib import Path

from scripts.consolidate_bacen_05_evidence import build_evidence


def write_json(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def sources(tmp_path: Path, *, validated: int = 0, pending: bool = True):
    risk = {
        "control_id": "BACEN-05",
        "vendor_count": 2,
        "status": "passed",
        "pending_legal_signoff_vendor_ids": ["T1", "T2"] if pending else [],
        "high_or_critical_risk_vendor_ids": ["T1"],
    }
    readiness = {
        "control_id": "BACEN-05",
        "technical_readiness_passed": True,
        "pending_vendor_ids": ["T1", "T2"] if pending else [],
        "summary": {"registered_vendors": 2},
    }
    contract = {
        "control_id": "BACEN-05",
        "result": "valid",
        "summary": {"validated_records": validated, "invalid_records": 0},
    }
    return (
        write_json(tmp_path, "risk.json", risk),
        write_json(tmp_path, "readiness.json", readiness),
        write_json(tmp_path, "contract.json", contract),
    )


def test_pending_real_evidence_keeps_control_partial(tmp_path: Path) -> None:
    report = build_evidence(*sources(tmp_path))
    assert report["control_status"] == "partial"
    assert report["automatic_blocking"] is False
    assert report["summary"]["validated_dpas"] == 0


def test_complete_real_evidence_allows_implemented(tmp_path: Path) -> None:
    report = build_evidence(*sources(tmp_path, validated=2, pending=False))
    assert report["control_status"] == "implemented"
    assert report["formal_requirements_complete"] is True


def test_vendor_count_mismatch_is_blocking(tmp_path: Path) -> None:
    risk, readiness, contract = sources(tmp_path)
    payload = json.loads(readiness.read_text())
    payload["summary"]["registered_vendors"] = 1
    readiness.write_text(json.dumps(payload), encoding="utf-8")
    report = build_evidence(risk, readiness, contract)
    assert report["automatic_blocking"] is True
    assert "vendor_count_mismatch" in report["findings"]
