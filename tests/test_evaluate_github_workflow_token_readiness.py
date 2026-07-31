from __future__ import annotations

import pytest

from scripts.evaluate_github_workflow_token_readiness import evaluate


def test_ready_decision_is_sanitized() -> None:
    report = evaluate(
        "ready",
        probe_branch="credential-probe/run-123",
        run_url="https://github.example/actions/runs/123",
    )

    assert report["decision"] == "validated"
    assert report["ready"] is True
    assert report["secret_value_logged"] is False
    assert report["secret_changed"] is False
    assert report["promotion_executed"] is False
    assert report["production_touched"] is False


@pytest.mark.parametrize(
    "stage",
    [
        "missing_secret",
        "authentication_failed",
        "repository_access_failed",
        "workflow_write_failed",
        "cleanup_failed",
    ],
)
def test_failure_stages_remain_blocked(stage: str) -> None:
    report = evaluate(stage, probe_branch="credential-probe/run-456", run_url="run:456")

    assert report["decision"] == "blocked"
    assert report["ready"] is False
    assert report["human_action_required"] is True
    assert report["secret_value_logged"] is False


def test_rejects_unknown_stage() -> None:
    with pytest.raises(ValueError, match="invalid readiness stage"):
        evaluate("unknown", probe_branch="probe", run_url="run")
