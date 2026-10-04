from datetime import datetime, timezone

from scripts.build_flow_completion_alert_state import build_state


def report(status="FAILED"):
    return {
        "summary": {"open": 1, "failed": int(status == "FAILED")},
        "open_items": [
            {
                "execution_id": "delivery-abc",
                "item_id": "commit-abc",
                "status": status,
                "expected_commit_sha": "abc",
                "next_expected": {"environment": "stg", "stage": "homologation"},
            }
        ],
    }


def test_emits_new_notification_once():
    now = datetime(2026, 7, 20, 20, 0, tzinfo=timezone.utc)
    first = build_state(report(), {}, now)
    second = build_state(report(), first, now)

    assert len(first["new_notifications"]) == 1
    assert second["new_notifications"] == []
    assert len(second["active_alerts"]) == 1


def test_status_change_generates_new_fingerprint():
    now = datetime(2026, 7, 20, 20, 0, tzinfo=timezone.utc)
    first = build_state(report("FAILED"), {}, now)
    second = build_state(report("BLOCKED"), first, now)

    assert len(second["new_notifications"]) == 1
    assert second["new_notifications"][0]["status"] == "BLOCKED"


def test_ignores_non_alert_status_and_limits_history():
    previous = {"history": [{"observed_at": str(index)} for index in range(200)]}
    state = build_state(report("IN_PROGRESS"), previous)

    assert state["active_alerts"] == []
    assert state["new_notifications"] == []
    assert len(state["history"]) == 168
    assert state["automatic_remediation_allowed"] is False
