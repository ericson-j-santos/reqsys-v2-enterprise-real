from datetime import datetime, timezone

from scripts.human_pending_auto_remediation import RemediationPolicy, decide


NOW = datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc)


def policy(*, suppress: bool = True) -> RemediationPolicy:
    return RemediationPolicy(
        issue_number=1520,
        workflow="example.yml",
        cooldown_minutes=60,
        inputs={},
        suppress_human_on_success=suppress,
    )


def run(status: str, conclusion: str | None, updated_at: str) -> dict:
    return {
        "status": status,
        "conclusion": conclusion,
        "updated_at": updated_at,
        "html_url": "https://example.test/run/1",
    }


def test_in_progress_suppresses_human_notification() -> None:
    result = decide(
        policy(),
        issue_open=True,
        runs=[run("in_progress", None, "2026-09-19T14:59:00Z")],
        now=NOW,
    )
    assert result["state"] == "in_progress"
    assert result["suppress_human"] is True
    assert result["dispatch_required"] is False


def test_recent_success_can_keep_real_human_followup_visible() -> None:
    result = decide(
        policy(suppress=False),
        issue_open=True,
        runs=[run("completed", "success", "2026-09-19T14:50:00Z")],
        now=NOW,
    )
    assert result["state"] == "recent_success"
    assert result["suppress_human"] is False


def test_recent_failure_is_not_suppressed() -> None:
    result = decide(
        policy(),
        issue_open=True,
        runs=[run("completed", "failure", "2026-09-19T14:50:00Z")],
        now=NOW,
    )
    assert result["state"] == "blocked"
    assert result["suppress_human"] is False
    assert result["dispatch_required"] is False


def test_stale_success_is_retried() -> None:
    result = decide(
        policy(),
        issue_open=True,
        runs=[run("completed", "success", "2026-09-19T12:00:00Z")],
        now=NOW,
    )
    assert result["state"] == "dispatch_required"
    assert result["dispatch_required"] is True


def test_closed_issue_is_never_dispatched() -> None:
    result = decide(policy(), issue_open=False, runs=[], now=NOW)
    assert result["state"] == "issue_closed"
    assert result["dispatch_required"] is False
