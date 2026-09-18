from datetime import UTC, datetime
from pathlib import Path

import yaml

from scripts.generate_bacen_executive_designation_lifecycle import build_report
from scripts.generate_bacen_executive_readiness import build_evidence

ROOT = Path(__file__).resolve().parents[1]
DESIGNATION = ROOT / "governance/bacen/EXECUTIVE-DESIGNATION.yaml"
REPORT = ROOT / "governance/bacen/ANNUAL-CYBERSECURITY-REPORT.md"
MATRIX = ROOT / "governance/bacen/BACEN-CONTROL-MATRIX.yaml"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_bacen08_development_defers_human_action_without_false_promotion() -> None:
    designation = load_yaml(DESIGNATION)
    assert designation["lifecycle_stage"] == "DEVELOPMENT"
    assert designation["institutional_designation_required"] is False
    assert designation["institutional_designation_gate_stage"] == "PRODUCTION"
    deferred = designation["deferred_institutional_governance"]
    assert deferred["enabled"] is True
    assert deferred["maximum_control_status"] == "partial"
    assert deferred["notification_policy"]["suppress_human_action_while_nonproduction"] is True
    assert deferred["production_gate"]["block_production_when_missing"] is True

    lifecycle = build_report(
        DESIGNATION,
        now=datetime(2026, 8, 13, tzinfo=UTC),
    )
    assert lifecycle["formal_designation_valid"] is False
    assert lifecycle["human_action_required"] is False
    assert lifecycle["automatic_blocking"] is False
    assert lifecycle["control_status"] == "partial"
    assert lifecycle["next_stage"] == "continue_technical_evidence_until_production_gate"

    readiness = build_evidence(REPORT, DESIGNATION)
    assert readiness["technical_readiness_passed"] is True
    assert readiness["formal_governance_complete"] is False
    assert readiness["readiness_status"] == "deferred_until_institutionalization"
    assert readiness["human_action_required"] is False
    assert readiness["automatic_blocking"] is False
    assert readiness["control_status"] == "partial"


def test_bacen08_production_gate_blocks_without_formal_governance(tmp_path: Path) -> None:
    designation = load_yaml(DESIGNATION)
    designation["lifecycle_stage"] = "PRODUCTION"
    designation["institutional_designation_required"] = True
    production_designation = tmp_path / "EXECUTIVE-DESIGNATION.yaml"
    production_designation.write_text(
        yaml.safe_dump(designation, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    lifecycle = build_report(
        production_designation,
        now=datetime(2026, 8, 13, tzinfo=UTC),
    )
    assert lifecycle["human_action_required"] is True
    assert lifecycle["automatic_blocking"] is True
    assert "formal_executive_designation_required_for_current_stage" in lifecycle["findings"]

    readiness = build_evidence(REPORT, production_designation)
    assert readiness["human_action_required"] is True
    assert readiness["automatic_blocking"] is True
    assert readiness["readiness_status"] == "formal_governance_required"
    assert "institutional_governance_required_for_current_stage" in readiness["findings"]


def test_matrix_keeps_deferred_controls_partial_until_production_gate() -> None:
    matrix = load_yaml(MATRIX)
    controls = {control["id"]: control for control in matrix["controls"]}

    bacen01 = controls["BACEN-01"]
    assert bacen01["status"] == "partial"
    assert bacen01["lifecycle_stage"] == "DEVELOPMENT"
    assert bacen01["approval_status"] == "deferred_until_institutionalization"
    assert bacen01["institutional_approval_gate_stage"] == "PRODUCTION"

    bacen08 = controls["BACEN-08"]
    assert bacen08["status"] == "partial"
    assert bacen08["lifecycle_stage"] == "DEVELOPMENT"
    assert bacen08["institutional_governance_status"] == "deferred_until_institutionalization"
    assert bacen08["institutional_governance_gate_stage"] == "PRODUCTION"
