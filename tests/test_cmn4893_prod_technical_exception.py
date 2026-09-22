from pathlib import Path

import yaml

from scripts.validate_bacen_production_readiness_authoritative import (
    authoritative_applicability,
    effective_applicability_for_target,
    validate_temporary_production_exception,
)


ROOT = Path(__file__).resolve().parents[1]
EXCEPTION = (
    ROOT
    / "governance"
    / "bacen"
    / "exceptions"
    / "CMN4893-SCOPE-DATA-PROD-TECHNICAL-EXCEPTION-2026-09-22.yaml"
)
DECISION = ROOT / "governance" / "bacen" / "normative" / "FAMILY-APPLICABILITY-DECISION.yaml"
NONPROD_POLICY = ROOT / "governance" / "bacen" / "NONPROD-TEMPORARY-TOLERANCE-POLICY.yaml"
HARD_GATE = ROOT / ".github" / "workflows" / "bacen-production-hard-gate.yml"
GATE2 = ROOT / ".github" / "workflows" / "bacen-production-readiness-gate2.yml"


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _authoritative() -> dict:
    return authoritative_applicability(_yaml(DECISION))


def test_exception_is_strictly_scoped_and_active_through_year_end() -> None:
    payload = _yaml(EXCEPTION)
    report = validate_temporary_production_exception(
        payload,
        authoritative=_authoritative(),
        as_of="2026-12-31T23:59:59Z",
    )

    assert report["active"] is True
    assert report["errors"] == []
    assert payload["allowed_scopes"] == ["prod"]
    assert payload["covered_blocker_codes"] == ["family_applicability_pending"]
    assert payload["temporarily_deferred_fields"] == [
        "institutional_scope.legal_entity",
        "institutional_scope.entity_type",
    ]
    assert payload["constraints"]["technical_production_deployment_may_be_evaluated"] is True
    assert payload["constraints"]["regulatory_finality_allowed"] is False
    assert payload["constraints"]["regulatory_compliance_claim_allowed"] is False
    assert payload["constraints"]["no_other_gate_bypass_allowed"] is True
    assert payload["constraints"]["fabricated_values_allowed"] is False
    assert payload["constraints"]["automatic_inference_allowed"] is False


def test_exception_expires_fail_closed_after_2026_12_31() -> None:
    report = validate_temporary_production_exception(
        _yaml(EXCEPTION),
        authoritative=_authoritative(),
        as_of="2027-01-01T00:00:00Z",
    )

    assert report["active"] is False
    assert "exception_expired" in report["errors"]


def test_exception_changes_only_effective_technical_decision_for_prod() -> None:
    authoritative = _authoritative()
    exception = validate_temporary_production_exception(
        _yaml(EXCEPTION),
        authoritative=authoritative,
        as_of="2026-09-22T19:00:00Z",
    )

    effective, resolved = effective_applicability_for_target(
        authoritative,
        exception,
        target_stage="PRODUCTION",
    )

    assert authoritative["decision"] == "pending_decision"
    assert effective["decision"] == "applicable"
    assert resolved["applied"] is True


def test_exception_never_applies_to_nonprod_or_after_real_decision() -> None:
    authoritative = _authoritative()
    exception = validate_temporary_production_exception(
        _yaml(EXCEPTION),
        authoritative=authoritative,
        as_of="2026-09-22T19:00:00Z",
    )

    effective_dev, resolved_dev = effective_applicability_for_target(
        authoritative,
        exception,
        target_stage="DEVELOPMENT",
    )
    assert effective_dev["decision"] == "pending_decision"
    assert resolved_dev["applied"] is False

    final_authoritative = dict(authoritative)
    final_authoritative["decision"] = "applicable"
    disabled = validate_temporary_production_exception(
        _yaml(EXCEPTION),
        authoritative=final_authoritative,
        as_of="2026-09-22T19:00:00Z",
    )
    effective_prod, resolved_prod = effective_applicability_for_target(
        final_authoritative,
        disabled,
        target_stage="PRODUCTION",
    )
    assert disabled["active"] is False
    assert disabled["reason"] == "authoritative_decision_is_final"
    assert effective_prod["decision"] == "applicable"
    assert resolved_prod["applied"] is False


def test_existing_nonprod_policy_remains_unchanged_and_prod_blocked_there() -> None:
    policy = _yaml(NONPROD_POLICY)
    assert policy["allowed_scopes"] == ["pull_request", "dev", "stg"]
    assert policy["blocked_scopes"] == ["prod"]


def test_prod_workflows_use_exception_without_broad_bypass() -> None:
    hard_gate = HARD_GATE.read_text(encoding="utf-8")
    gate2 = GATE2.read_text(encoding="utf-8")
    exception_name = "CMN4893-SCOPE-DATA-PROD-TECHNICAL-EXCEPTION-2026-09-22.yaml"

    assert exception_name in hard_gate
    assert exception_name in gate2
    assert "temporary_production_exception_active" in hard_gate
    assert "regulatory_finality_allowed" in hard_gate
    assert "legacy_allowed and gate2_allowed" in hard_gate
    assert "production_deployment_allowed" in hard_gate
