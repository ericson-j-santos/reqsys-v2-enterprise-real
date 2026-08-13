import json
from pathlib import Path

import yaml

from scripts.consolidate_bacen_05_evidence import build_evidence as consolidate
from scripts.generate_bacen_vendor_dpa_readiness import build_evidence


def write_yaml(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def register(tmp_path: Path) -> Path:
    return write_yaml(
        tmp_path / "register.yaml",
        {"providers": [{"id": "T1"}, {"id": "T2"}]},
    )


def manifest(tmp_path: Path, lifecycle_stage: str, approved: bool = False) -> Path:
    status = "formally_approved" if approved else "pending_verification"
    legal = "formally_approved" if approved else "pending"
    return write_yaml(
        tmp_path / "manifest.yaml",
        {
            "lifecycle_stage": lifecycle_stage,
            "vendors": [
                {
                    "id": vendor_id,
                    "data_processing_terms": status,
                    "data_location": status,
                    "subprocessors": status,
                    "portability": status,
                    "termination_and_deletion": status,
                    "legal_signoff": legal,
                }
                for vendor_id in ("T1", "T2")
            ],
            "deferred_vendor_governance": {
                "enabled": True,
                "production_gate": {
                    "validated_dpa_evidence_required": True,
                    "formal_legal_signoff_required": True,
                    "block_production_when_missing": True,
                },
            },
            "production_touched": False,
        },
    )


def test_development_defers_formal_vendor_governance(tmp_path: Path) -> None:
    evidence = build_evidence(register(tmp_path), manifest(tmp_path, "DEVELOPMENT"))

    assert evidence["lifecycle_stage"] == "DEVELOPMENT"
    assert evidence["control_status"] == "partial"
    assert evidence["technical_readiness_passed"] is True
    assert evidence["formal_dpa_and_legal_signoff_complete"] is False
    assert evidence["readiness_status"] == "deferred_until_institutionalization"
    assert evidence["human_action_required"] is False
    assert evidence["external_evidence_required"] is False
    assert evidence["production_gate_blocking"] is False
    assert evidence["automatic_blocking"] is False


def test_production_reactivates_formal_vendor_governance(tmp_path: Path) -> None:
    evidence = build_evidence(register(tmp_path), manifest(tmp_path, "PRODUCTION"))

    assert evidence["control_status"] == "partial"
    assert evidence["readiness_status"] == "formal_vendor_governance_required"
    assert evidence["human_action_required"] is True
    assert evidence["external_evidence_required"] is True
    assert evidence["production_gate_blocking"] is True
    assert evidence["automatic_blocking"] is True


def test_formal_completion_can_implement_control(tmp_path: Path) -> None:
    evidence = build_evidence(
        register(tmp_path),
        manifest(tmp_path, "PRODUCTION", approved=True),
    )

    assert evidence["control_status"] == "implemented"
    assert evidence["formal_dpa_and_legal_signoff_complete"] is True
    assert evidence["human_action_required"] is False
    assert evidence["automatic_blocking"] is False


def test_consolidated_development_evidence_remains_partial_without_human_block(tmp_path: Path) -> None:
    readiness = build_evidence(register(tmp_path), manifest(tmp_path, "DEVELOPMENT"))
    risk = write_json(
        tmp_path / "risk.json",
        {
            "control_id": "BACEN-05",
            "vendor_count": 2,
            "status": "passed",
            "pending_legal_signoff_vendor_ids": ["T1", "T2"],
            "high_or_critical_risk_vendor_ids": [],
        },
    )
    readiness_path = write_json(tmp_path / "readiness.json", readiness)
    contract = write_json(
        tmp_path / "contract.json",
        {
            "control_id": "BACEN-05",
            "result": "valid",
            "summary": {"validated_records": 0, "invalid_records": 0},
        },
    )

    report = consolidate(risk, readiness_path, contract)

    assert report["control_status"] == "partial"
    assert report["readiness_status"] == "deferred_until_institutionalization"
    assert report["human_action_required"] is False
    assert report["external_evidence_required"] is False
    assert report["production_gate_blocking"] is False
    assert report["automatic_blocking"] is False
