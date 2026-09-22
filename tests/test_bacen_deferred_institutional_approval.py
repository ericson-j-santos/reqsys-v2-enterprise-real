from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "governance/bacen/CYBERSECURITY-POLICY-METADATA.yaml"
RECONCILIATION = ROOT / "governance/bacen/BACEN-GOVERNANCE-RECONCILIATION.yaml"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_bacen01_development_defers_institutional_approval_without_false_promotion():
    data = load_yaml(METADATA)
    assert data["lifecycle_stage"] == "DEVELOPMENT"
    assert data["compliance_status"] == "technically_implemented"
    assert data["institutional_approval_required"] is False
    assert data["approval_authority"] == "pending_formal_designation"
    assert data["approval_record"] is None
    deferred = data["deferred_institutional_approval"]
    assert deferred["enabled"] is True
    assert deferred["maximum_compliance_status"] == "technically_implemented"
    assert deferred["notification_policy"]["suppress_human_action_while_nonproduction"] is True


def test_bacen01_production_gate_requires_formal_fields():
    data = load_yaml(METADATA)
    gate = data["deferred_institutional_approval"]["production_gate"]
    assert data["institutional_approval_gate_stage"] == "PRODUCTION"
    assert gate["approval_authority_required"] is True
    assert gate["approval_record_required"] is True
    assert gate["institutional_approval_date_required"] is True
    assert gate["block_production_when_missing"] is True


def test_reconciliation_marks_no_human_action_during_development():
    data = load_yaml(RECONCILIATION)
    control = next(item for item in data["controls"] if item["control_id"] == "BACEN-01")
    assert control["lifecycle_stage"] == "DEVELOPMENT"
    assert control["human_action_required_now"] is False
    assert control["canonicalization_status"] == "deferred_by_lifecycle"
    assert control["production_gate"]["block_when_deferred_requirements_missing"] is True
