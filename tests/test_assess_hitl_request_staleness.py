from datetime import UTC, datetime

import pytest

from scripts.assess_hitl_request_staleness import assess_requests


NOW = datetime(2026, 7, 31, 17, 0, tzinfo=UTC)


def issue(number: int, updated_at: str, *, labeled: bool = True) -> dict:
    labels = [{"name": "hitl-approval-request"}] if labeled else [{"name": "other"}]
    return {
        "number": number,
        "title": f"[HITL][BACEN-0{number}] Decisao formal",
        "url": f"https://github.com/example/repo/issues/{number}",
        "updatedAt": updated_at,
        "labels": labels,
    }


def test_classifies_fresh_reminder_and_escalation() -> None:
    report = assess_requests(
        [
            issue(1, "2026-07-31T12:00:00Z"),
            issue(2, "2026-07-30T12:00:00Z"),
            issue(3, "2026-07-27T12:00:00Z"),
            issue(4, "2026-07-20T12:00:00Z", labeled=False),
        ],
        now=NOW,
        reminder_after_hours=24,
        escalation_after_hours=72,
    )

    assert report["summary"] == {
        "open_requests": 3,
        "fresh": 1,
        "reminder_due": 1,
        "escalation_due": 1,
    }
    assert report["decision"] == "escalation_required"
    assert report["items"][0]["issue_number"] == 3
    assert report["automatic_approval_allowed"] is False
    assert report["production_touched"] is False


def test_no_action_when_requests_are_recent() -> None:
    report = assess_requests(
        [issue(1, "2026-07-31T16:00:00Z")],
        now=NOW,
        reminder_after_hours=24,
        escalation_after_hours=72,
    )
    assert report["decision"] == "no_action_required"


@pytest.mark.parametrize(
    ("reminder", "escalation"),
    [(0, 72), (24, 24), (72, 24)],
)
def test_rejects_invalid_policy(reminder: int, escalation: int) -> None:
    with pytest.raises(ValueError):
        assess_requests(
            [],
            now=NOW,
            reminder_after_hours=reminder,
            escalation_after_hours=escalation,
        )
