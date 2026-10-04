from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXCEPTION = (
    ROOT
    / "governance"
    / "bacen"
    / "exceptions"
    / "CMN4893-SCOPE-DATA-TEMPORARY-EXCEPTION-2026-09-18.yaml"
)
POLICY = ROOT / "governance" / "bacen" / "NONPROD-TEMPORARY-TOLERANCE-POLICY.yaml"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_cmn4893_exception_allows_only_nonprod_and_preserves_fail_closed() -> None:
    exception = load_yaml(EXCEPTION)
    policy = load_yaml(POLICY)

    assert exception["status"] == "active"
    assert exception["exception_id"] == (
        "REQSYS-BACEN-CMN4893-SCOPE-DATA-EXCEPTION-2026-09-18"
    )
    assert exception["allowed_scopes"] == ["pull_request", "dev", "stg"]
    assert exception["blocked_scopes"] == ["prod"]
    assert set(exception["allowed_scopes"]).issubset(set(policy["allowed_scopes"]))
    assert set(exception["blocked_scopes"]).issubset(set(policy["blocked_scopes"]))

    constraints = exception["constraints"]
    assert constraints["production_allowed"] is False
    assert constraints["regulatory_finality_allowed"] is False
    assert constraints["fabricated_values_allowed"] is False
    assert constraints["automatic_inference_allowed"] is False
    assert constraints["authoritative_decision_must_remain"] == "pending_decision"

    assert exception["temporarily_deferred_fields"] == [
        "institutional_scope.legal_entity",
        "institutional_scope.entity_type",
    ]
    assert exception["audit"]["production_touched"] is False
    assert exception["audit"]["replaces_regulatory_evidence"] is False


def test_cmn4893_exception_expiry_requires_explicit_human_renewal() -> None:
    exception = load_yaml(EXCEPTION)

    validity = exception["validity"]
    assert str(validity["valid_until"]) == "2026-10-12"
    assert validity["renewal_requires_explicit_human_approval"] is True
    assert validity["inherits_policy"] == (
        "governance/bacen/NONPROD-TEMPORARY-TOLERANCE-POLICY.yaml"
    )
