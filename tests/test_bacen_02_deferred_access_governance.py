import json
from pathlib import Path

import yaml

from scripts.consolidate_bacen_02_access_mfa_readiness import consolidate
from scripts.generate_bacen_access_review_readiness import build_evidence
from scripts.validate_bacen_idp_mfa_evidence import load_document, validate

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "governance/bacen/ACCESS-REVIEW-REGISTER.yaml"
MFA_CONTRACT = ROOT / "governance/bacen/IDP-MFA-EVIDENCE-CONTRACT.json"
MATRIX = ROOT / "governance/bacen/BACEN-CONTROL-MATRIX.yaml"


def test_bacen02_development_defers_formal_review_and_external_mfa(tmp_path: Path) -> None:
    access = build_evidence(REGISTER)
    assert access["lifecycle_stage"] == "DEVELOPMENT"
    assert access["control_status"] == "partial"
    assert access["formal_review_completed"] is False
    assert access["mfa_evidenced"] is False
    assert access["human_action_required"] is False
    assert access["external_evidence_required"] is False
    assert access["automatic_blocking"] is False
    assert access["readiness_status"] == "deferred_until_institutionalization"

    mfa = validate(load_document(MFA_CONTRACT), MFA_CONTRACT)
    assert mfa["mfa_evidenced"] is False
    assert mfa["structural_checks_passed"] is True

    access_path = tmp_path / "access.json"
    mfa_path = tmp_path / "mfa.json"
    access_path.write_text(json.dumps(access), encoding="utf-8")
    mfa_path.write_text(json.dumps(mfa), encoding="utf-8")

    consolidated = consolidate(access_path, mfa_path)
    assert consolidated["control_status"] == "partial"
    assert consolidated["readiness_status"] == "deferred_until_institutionalization"
    assert consolidated["pending_actions"] == []
    assert consolidated["deferred_actions"] == [
        "complete_formal_quarterly_access_review",
        "provide_validated_identity_provider_mfa_evidence",
    ]
    assert consolidated["human_action_required"] is False
    assert consolidated["external_evidence_required"] is False
    assert consolidated["automatic_blocking"] is False


def test_bacen02_matrix_preserves_partial_and_defers_institutional_action() -> None:
    matrix = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
    control = next(item for item in matrix["controls"] if item["id"] == "BACEN-02")
    assert control["status"] == "partial"
    assert control["lifecycle_stage"] == "DEVELOPMENT"
    assert control["institutional_governance_status"] == "deferred_until_institutionalization"
    assert control["institutional_governance_gate_stage"] == "PRODUCTION"
