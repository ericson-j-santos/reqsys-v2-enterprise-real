import pytest

from scripts.build_stg_enforcement_approval import build_record


def history(status="ready_for_human_approval"):
    return {
        "contract": "reqsys-environment-promotion-history",
        "stg_enforcement_maturity": {
            "status": status,
            "automatic_change_allowed": False,
            "required_window": 5,
            "observed_window": 5,
            "approved_count": 4,
            "valid_count": 5,
            "blocking_count": 0,
            "criteria_met": status == "ready_for_human_approval",
        }
    }


def kwargs():
    return {
        "approval_scope": "policy_change",
        "approver": "github:governance-owner",
        "approver_type": "User",
        "rationale": "Cinco execuções válidas e estabilidade observada.",
        "ticket": "REQSYS-1004",
        "source_pr_number": "1292",
        "source_run_id": "29799999999",
        "source_sha": "1234567890abcdef1234567890abcdef12345678",
        "generated_at": "2026-07-21T02:00:00+00:00",
    }


def test_approval_requires_ready_evidence():
    record = build_record(history(), decision="approve", **kwargs())
    assert record["status"] == "approved_for_policy_change"
    assert record["effective_approval"] is True
    assert record["next_action"] == "authorize_bound_policy_pr"


def test_approval_is_blocked_when_maturity_is_not_ready():
    record = build_record(history("collecting_evidence"), decision="approve", **kwargs())
    assert record["status"] == "blocked_by_evidence"
    assert record["effective_approval"] is False


def test_exception_retirement_accepts_canonical_collecting_history():
    inputs = kwargs()
    inputs["approval_scope"] = "exception_retirement"
    payload = history("collecting_evidence")
    payload["stg_enforcement_maturity"]["approved_count"] = 0
    record = build_record(payload, decision="approve", **inputs)
    assert record["status"] == "approved_for_exception_retirement"
    assert record["effective_approval"] is True
    assert record["next_action"] == "retire_expired_exception_on_bound_pr"


def test_rejection_preserves_current_policy():
    record = build_record(history(), decision="reject", **kwargs())
    assert record["status"] == "rejected"
    assert record["next_action"] == "preserve_current_policy"


def test_record_never_changes_policy_or_deploys():
    record = build_record(history(), decision="approve", **kwargs())
    assert record["automatic_policy_change"] is False
    assert record["automatic_deploy"] is False


def test_legacy_maturity_key_never_authorizes():
    legacy = history()
    legacy["stg_maturity"] = legacy.pop("stg_enforcement_maturity")
    record = build_record(legacy, decision="approve", **kwargs())
    assert record["status"] == "blocked_by_evidence"
    assert record["effective_approval"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("criteria_met", False),
        ("automatic_change_allowed", True),
        ("observed_window", 4),
        ("valid_count", 4),
        ("blocking_count", 1),
    ],
)
def test_inconsistent_canonical_maturity_never_authorizes(field, value):
    payload = history()
    payload["stg_enforcement_maturity"][field] = value
    record = build_record(payload, decision="approve", **kwargs())
    assert record["effective_approval"] is False


@pytest.mark.parametrize("approver", ["github-actions[bot]", "github:dependabot[bot]", "owner"])
def test_non_human_or_unverified_approver_is_rejected(approver):
    inputs = kwargs()
    inputs["approver"] = approver
    with pytest.raises(ValueError, match="authenticated human GitHub actor"):
        build_record(history(), decision="approve", **inputs)


def test_non_user_actor_type_is_rejected():
    inputs = kwargs()
    inputs["approver_type"] = "Bot"
    with pytest.raises(ValueError, match="approver_type must be User"):
        build_record(history(), decision="approve", **inputs)


def test_correlation_id_is_deterministic():
    first = build_record(history(), decision="approve", **kwargs())
    second = build_record(history(), decision="approve", **kwargs())
    assert first["correlation_id"] == second["correlation_id"]
