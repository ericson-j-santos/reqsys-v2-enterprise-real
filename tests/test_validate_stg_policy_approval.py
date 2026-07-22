from scripts.validate_stg_policy_approval import validate


def approval(**overrides):
    payload = {
        "contract": "reqsys-stg-enforcement-approval",
        "status": "approved_for_policy_change",
        "requested_decision": "approve",
        "effective_approval": True,
        "correlation_id": "stg-approval-42",
        "approval": {
            "approver": "governance-owner",
            "rationale": "STG atingiu maturidade observada.",
            "ticket": "CHG-1004",
        },
        "evidence": {
            "source_sha": "abc123",
            "source_run_id": "42",
        },
    }
    payload.update(overrides)
    return payload


def test_valid_approval_authorizes_policy_change():
    result = validate(approval(), "abc123", "42")
    assert result["valid"] is True
    assert result["decision"] == "authorized"


def test_missing_artifact_blocks():
    result = validate({}, "abc123")
    assert result["valid"] is False
    assert "approval_artifact_missing" in result["reasons"]


def test_rejection_blocks():
    result = validate(
        approval(
            status="rejected",
            requested_decision="reject",
            effective_approval=False,
        ),
        "abc123",
        "42",
    )
    assert result["valid"] is False
    assert "approval_not_effective" in result["reasons"]


def test_sha_mismatch_blocks():
    payload = approval()
    payload["evidence"]["source_sha"] = "other"
    result = validate(payload, "abc123", "42")
    assert "approval_sha_mismatch" in result["reasons"]


def test_run_id_mismatch_blocks():
    payload = approval()
    payload["evidence"]["source_run_id"] = "99"
    result = validate(payload, "abc123", "42")
    assert "approval_run_id_mismatch" in result["reasons"]
