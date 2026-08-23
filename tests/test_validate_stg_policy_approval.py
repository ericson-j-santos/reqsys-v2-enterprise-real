from scripts.validate_stg_policy_approval import validate


def approval(**overrides):
    payload = {
        "contract": "reqsys-stg-enforcement-approval",
        "status": "approved_for_policy_change",
        "requested_decision": "approve",
        "approval_scope": "policy_change",
        "effective_approval": True,
        "approval_mode": "human_workflow_dispatch",
        "automatic_policy_change": False,
        "automatic_deploy": False,
        "correlation_id": "stg-approval-42",
        "approval": {
            "approver": "github:governance-owner",
            "actor_type": "User",
            "rationale": "STG atingiu maturidade observada.",
            "ticket": "CHG-1004",
        },
        "evidence": {
            "history_contract_valid": True,
            "maturity_status": "ready_for_human_approval",
            "ready_for_human_approval": True,
            "policy_change_ready": True,
            "exception_retirement_evidence_valid": True,
            "criteria_met": True,
            "automatic_change_allowed": False,
            "source_pr_number": 1292,
            "source_sha": "abc123",
            "source_run_id": "42",
        },
    }
    payload.update(overrides)
    return payload


def test_valid_approval_authorizes_policy_change():
    result = validate(approval(), "abc123", "42", "1292")
    assert result["valid"] is True
    assert result["decision"] == "authorized"


def test_valid_scoped_approval_authorizes_exception_retirement():
    payload = approval(
        status="approved_for_exception_retirement",
        approval_scope="exception_retirement",
    )
    payload["evidence"]["maturity_status"] = "collecting_evidence"
    payload["evidence"]["ready_for_human_approval"] = False
    payload["evidence"]["criteria_met"] = False
    payload["evidence"]["policy_change_ready"] = False
    result = validate(payload, "abc123", "42", "1292", "exception_retirement")
    assert result["valid"] is True
    assert result["decision"] == "authorized"


def test_retirement_scope_cannot_authorize_policy_change():
    payload = approval(
        status="approved_for_exception_retirement",
        approval_scope="exception_retirement",
    )
    result = validate(payload, "abc123", "42", "1292", "policy_change")
    assert "approval_scope_mismatch" in result["reasons"]


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


def test_pr_number_mismatch_blocks():
    result = validate(approval(), "abc123", "42", "9999")
    assert "approval_pr_number_mismatch" in result["reasons"]


def test_bot_actor_blocks():
    payload = approval()
    payload["approval"]["approver"] = "github:github-actions[bot]"
    result = validate(payload, "abc123", "42", "1292")
    assert "approval_actor_not_authenticated_human" in result["reasons"]


def test_non_user_actor_type_blocks():
    payload = approval()
    payload["approval"]["actor_type"] = "Bot"
    result = validate(payload, "abc123", "42", "1292")
    assert "approval_actor_type_not_user" in result["reasons"]


def test_legacy_or_automated_approval_mode_blocks():
    payload = approval(approval_mode="automatic-temporary")
    result = validate(payload, "abc123", "42", "1292")
    assert "approval_mode_not_human_dispatch" in result["reasons"]


def test_noncanonical_maturity_evidence_blocks():
    payload = approval()
    payload["evidence"]["history_contract_valid"] = False
    payload["evidence"]["criteria_met"] = False
    result = validate(payload, "abc123", "42", "1292")
    assert "approval_history_contract_invalid" in result["reasons"]
    assert "approval_criteria_not_met" in result["reasons"]


def test_automatic_side_effect_flags_block():
    payload = approval(automatic_policy_change=True, automatic_deploy=True)
    result = validate(payload, "abc123", "42", "1292")
    assert "automatic_policy_change_not_disabled" in result["reasons"]
    assert "automatic_deploy_not_disabled" in result["reasons"]
