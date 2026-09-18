from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_bacen_production_gate.py"
spec = importlib.util.spec_from_file_location("validate_bacen_production_gate", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _matrix() -> dict:
    return {
        "controls": [
            {
                "id": "BACEN-01",
                "status": "partial",
                "decision_status": "approval_comment_recorded_deferred_until_institutionalization",
                "approval_status": "deferred_until_institutionalization",
            },
            {
                "id": "BACEN-08",
                "status": "partial",
                "decision_status": "approval_comment_recorded_deferred_until_institutionalization",
                "institutional_governance_status": "deferred_until_institutionalization",
                "executive_designation_status": "pending_formal_designation",
                "report_signoff_status": "pending_formal_signoff",
            },
        ]
    }


def _reconciliation() -> dict:
    return {
        "controls": [
            {
                "control_id": "BACEN-01",
                "deferred_requirements": [
                    "formal_approval_authority",
                    "signed_attestation_reference",
                    "institutional_approval_date",
                ],
                "production_gate": {
                    "required": True,
                    "block_when_deferred_requirements_missing": True,
                },
            },
            {
                "control_id": "BACEN-08",
                "deferred_requirements": [
                    "formal_executive_designation",
                    "designated_by",
                    "formal_report_signoff",
                    "report_signed_by",
                    "report_signed_at",
                ],
                "production_gate": {
                    "required": True,
                    "block_when_deferred_requirements_missing": True,
                },
            },
        ]
    }


def test_production_gate_blocks_deferred_bacen_01_and_bacen_08() -> None:
    report = module.evaluate_gate(
        _matrix(),
        _reconciliation(),
        target_stage="PRODUCTION",
    )

    assert report["decision"] == "blocked"
    assert report["production_touched"] is False
    assert report["automatic_override_allowed"] is False
    assert {item["control_id"] for item in report["blockers"]} == {"BACEN-01", "BACEN-08"}
    assert "signed_attestation_reference" in report["blockers"][0]["reasons"][2]


def test_deferred_controls_are_allowed_before_production_only() -> None:
    report = module.evaluate_gate(
        _matrix(),
        _reconciliation(),
        target_stage="DEVELOPMENT",
    )

    assert report["decision"] == "allowed"
    assert report["blockers"] == []
    assert all(item["decision"] == "deferred_allowed_before_production" for item in report["observations"])


def test_production_gate_allows_when_formal_controls_are_canonicalized() -> None:
    matrix = _matrix()
    reconciliation = _reconciliation()
    for control in matrix["controls"]:
        control["status"] = "implemented"
        control["decision_status"] = "approval_formally_canonicalized"
        control.pop("approval_status", None)
        control.pop("institutional_governance_status", None)
    for control in reconciliation["controls"]:
        control["deferred_requirements"] = []

    report = module.evaluate_gate(matrix, reconciliation, target_stage="PRODUCTION")

    assert report["decision"] == "allowed"
    assert report["blockers"] == []


def test_repository_state_currently_blocks_production_until_formal_fields_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    report = module.evaluate_gate(
        module.load_yaml(root / "governance" / "bacen" / "BACEN-CONTROL-MATRIX.yaml"),
        module.load_yaml(root / "governance" / "bacen" / "BACEN-GOVERNANCE-RECONCILIATION.yaml"),
        target_stage="PRODUCTION",
    )

    assert report["decision"] == "blocked"
    assert {item["control_id"] for item in report["blockers"]} == {"BACEN-01", "BACEN-08"}
