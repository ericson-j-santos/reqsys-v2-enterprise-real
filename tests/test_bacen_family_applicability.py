from pathlib import Path

import yaml

from scripts.validate_bacen_family_applicability import validate_family_applicability
from scripts.validate_bacen_production_readiness_authoritative import authoritative_applicability


def _record(decision: str = "pending_decision") -> dict:
    return {
        "schema_version": "1.0.0",
        "record": "bacen_family_applicability_decision",
        "uid": "applicability-cmn4893-test",
        "family": "CMN-4893",
        "decision": decision,
        "decided_by": None,
        "decided_at": None,
        "rationale": None,
        "approval_reference": None,
        "institutional_scope": {
            "legal_entity": None,
            "entity_type": None,
            "regulator_scope": None,
            "rsfn_connection": "unknown",
            "pix_participant": "unknown",
            "str_participant": "unknown",
            "smf_scope": "unknown",
        },
        "regulatory_basis": [
            {"regulation": "CMN-4893-2021", "role": "base"},
            {"regulation": "CMN-5274-2025", "role": "amendment"},
        ],
        "constraints": {
            "human_authority_required": True,
            "automatic_inference_allowed": False,
            "automatic_override_allowed": False,
        },
    }


def _complete(record: dict) -> dict:
    record["decided_by"] = "autoridade-institucional"
    record["decided_at"] = "2026-09-05T02:00:00Z"
    record["rationale"] = "Decisão formal baseada no enquadramento institucional aprovado."
    record["approval_reference"] = "GRC-DECISION-2026-001"
    record["institutional_scope"]["legal_entity"] = "entidade-regulada"
    record["institutional_scope"]["entity_type"] = "instituicao_financeira"
    return record


def test_pending_decision_is_valid_but_not_final() -> None:
    report = validate_family_applicability(_record())
    assert report["result"] == "valid_with_pending_decision"
    assert report["decision_is_final"] is False


def test_applicable_requires_authority_and_approval_trace() -> None:
    report = validate_family_applicability(_record("applicable"))
    assert report["result"] == "invalid"
    assert "applicable exige decided_by" in report["errors"]
    assert "applicable exige approval_reference" in report["errors"]
    assert "applicable exige institutional_scope.legal_entity" in report["errors"]


def test_not_applicable_requires_same_formal_trace() -> None:
    report = validate_family_applicability(_record("not_applicable"))
    assert report["result"] == "invalid"
    assert "not_applicable exige decided_by" in report["errors"]
    assert "not_applicable exige approval_reference" in report["errors"]


def test_complete_applicable_decision_is_valid() -> None:
    report = validate_family_applicability(_complete(_record("applicable")))
    assert report["result"] == "valid"
    assert report["decision_is_final"] is True
    assert report["automatic_inference_allowed"] is False


def test_authoritative_adapter_preserves_approval_metadata() -> None:
    applicability = authoritative_applicability(_complete(_record("applicable")))
    assert applicability["decision"] == "applicable"
    assert applicability["approval_reference"] == "GRC-DECISION-2026-001"
    assert applicability["record_uid"] == "applicability-cmn4893-test"


def test_repository_record_remains_pending_without_human_decision() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = yaml.safe_load(
        (root / "governance/bacen/normative/FAMILY-APPLICABILITY-DECISION.yaml").read_text(encoding="utf-8")
    )
    report = validate_family_applicability(payload)
    assert payload["decision"] == "pending_decision"
    assert report["result"] == "valid_with_pending_decision"
    assert payload["constraints"]["human_authority_required"] is True
    assert payload["constraints"]["automatic_inference_allowed"] is False
