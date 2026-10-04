import pytest

from scripts.build_bacen_formal_completion_proposal import build_proposal


def matrix(status: str = "partial") -> dict:
    return {
        "controls": [
            {
                "id": "BACEN-08",
                "status": status,
                "evidence": "artifacts/bacen/bacen-08-executive-readiness.json",
            }
        ]
    }


def decision(*, status: str = "approved", actor: str = "human-reviewer") -> dict:
    return {
        "contract": "reqsys-hitl-approval-decision",
        "status": status,
        "effective_decision": "approve" if status == "approved" else "reject",
        "approval": {"actor": actor, "permission": "write"},
        "evidence": {
            "immutable_reference": "https://github.com/example/repo/issues/1119#issuecomment-1"
        },
    }


def issue() -> dict:
    return {
        "title": "[HITL][BACEN-08] Designacao executiva",
        "body": "Controle BACEN-08",
        "url": "https://github.com/example/repo/issues/1119",
    }


def test_builds_non_applying_human_review_proposal() -> None:
    report = build_proposal(matrix=matrix(), issue=issue(), decision=decision())
    assert report["control_id"] == "BACEN-08"
    assert report["candidate_status"] == "implemented"
    assert report["decision"] == "human_review_required"
    assert report["automatic_apply_allowed"] is False
    assert report["automatic_implementation_claim_allowed"] is False
    assert report["production_touched"] is False


def test_is_noop_when_control_is_already_implemented() -> None:
    report = build_proposal(
        matrix=matrix("implemented"),
        issue=issue(),
        decision=decision(),
    )
    assert report["decision"] == "no_change_required"
    assert report["human_review_required"] is False


@pytest.mark.parametrize(
    "invalid_decision",
    [
        decision(status="rejected"),
        decision(actor="github-actions[bot]"),
    ],
)
def test_rejects_invalid_decision(invalid_decision: dict) -> None:
    with pytest.raises(ValueError):
        build_proposal(matrix=matrix(), issue=issue(), decision=invalid_decision)
