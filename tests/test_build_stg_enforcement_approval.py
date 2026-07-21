from scripts.build_stg_enforcement_approval import build_record


def history(status="ready_for_human_approval"):
    return {
        "stg_maturity": {
            "status": status,
            "window_size": 5,
            "approved_count": 4,
            "blocked_count": 0,
            "insufficient_evidence_count": 0,
        }
    }


def kwargs():
    return {
        "approver": "governance-owner",
        "rationale": "Cinco execuções válidas e estabilidade observada.",
        "ticket": "REQSYS-1004",
        "source_run_id": "29799999999",
        "source_sha": "1234567890abcdef",
        "generated_at": "2026-07-21T02:00:00+00:00",
    }


def test_approval_requires_ready_evidence():
    record = build_record(history(), decision="approve", **kwargs())
    assert record["status"] == "approved_for_policy_change"
    assert record["effective_approval"] is True
    assert record["next_action"] == "open_policy_change_pr"


def test_approval_is_blocked_when_maturity_is_not_ready():
    record = build_record(history("collecting_evidence"), decision="approve", **kwargs())
    assert record["status"] == "blocked_by_evidence"
    assert record["effective_approval"] is False


def test_rejection_preserves_warning_only():
    record = build_record(history(), decision="reject", **kwargs())
    assert record["status"] == "rejected"
    assert record["next_action"] == "preserve_warning_only"


def test_record_never_changes_policy_or_deploys():
    record = build_record(history(), decision="approve", **kwargs())
    assert record["automatic_policy_change"] is False
    assert record["automatic_deploy"] is False


def test_correlation_id_is_deterministic():
    first = build_record(history(), decision="approve", **kwargs())
    second = build_record(history(), decision="approve", **kwargs())
    assert first["correlation_id"] == second["correlation_id"]
