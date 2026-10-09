"""No-external-effects tests for the authorized Teams E2E admission gate."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.authorized_teams_e2e_admission import AdmissionError, COMMAND, decide

SHA = "a" * 40
WORKFLOW = Path(".github/workflows/reqsys-authorized-actions-gateway.yml")


def _instant(seconds: int) -> str:
    return (datetime(2026, 10, 9, 15, 18, 45, tzinfo=timezone.utc)
            + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _event(comment_id: int, seconds: int = 0, *, command: str = COMMAND, user: str = "ericson-j-santos"):
    return {
        "action": "created",
        "issue": {"number": 1705},
        "comment": {"id": comment_id, "created_at": _instant(seconds),
                    "body": command, "user": {"login": user}},
    }


def _record(comment_id: int, seconds: int):
    return {"id": comment_id, "created_at": _instant(seconds)}


def test_first_comment_is_admitted_without_effect():
    result = decide(_event(100), [_record(100, 0)], expected_sha=SHA)
    assert result["admitted"] is True
    assert result["canonical_comment_id"] == 100
    assert result["status"] == "admitted"


def test_second_simultaneous_authorized_comment_is_suppressed():
    comments = [_record(100, 0), _record(101, 3)]
    assert decide(_event(100), comments, expected_sha=SHA)["admitted"] is True
    result = decide(_event(101, 3), comments, expected_sha=SHA)
    assert result["admitted"] is False
    assert result["canonical_comment_id"] == 100
    assert result["status"] == "duplicate_suppressed"


def test_later_repetition_outside_window_is_allowed():
    result = decide(_event(102, 121),
                    [_record(100, 0), _record(102, 121)], expected_sha=SHA)
    assert result["admitted"] is True


def test_same_instant_uses_immutable_comment_id_as_order():
    comments = [_record(103, 0), _record(104, 0)]
    assert decide(_event(103), comments, expected_sha=SHA)["admitted"] is True
    assert decide(_event(104), comments, expected_sha=SHA)["admitted"] is False


@pytest.mark.parametrize("mutation", [
    lambda event: event["issue"].update(number=1706),
    lambda event: event["comment"]["user"].update(login="different-user"),
    lambda event: event["comment"].update(body="another-command"),
    lambda event: event.update(action="edited"),
])
def test_unauthorized_or_mutated_event_fails_closed(mutation):
    event = _event(100)
    mutation(event)
    with pytest.raises(AdmissionError):
        decide(event, [_record(100, 0)], expected_sha=SHA)


def test_missing_current_comment_or_incomplete_readback_fails_closed():
    with pytest.raises(AdmissionError, match="current_comment_not_uniquely_read_back"):
        decide(_event(101, 3), [_record(100, 0)], expected_sha=SHA)
    with pytest.raises(AdmissionError, match="current_comment_not_uniquely_read_back"):
        decide(_event(100), [_record(100, 0), _record(100, 0)], expected_sha=SHA)


def test_corrupt_sha_timestamp_and_record_fail_closed():
    with pytest.raises(AdmissionError, match="expected_main_sha_invalid"):
        decide(_event(100), [_record(100, 0)], expected_sha="bad")
    with pytest.raises(AdmissionError, match="comment_timestamp_without_timezone"):
        decide(_event(100), [{"id": 100, "created_at": "2026-10-09T15:18:45"}],
               expected_sha=SHA)
    with pytest.raises(AdmissionError, match="comment_record_invalid"):
        decide(_event(100), [None], expected_sha=SHA)


def test_workflow_preserves_comment_scoped_concurrency_and_blocks_duplicate_dispatch():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "group: reqsys-authorized-actions-gateway-${{ github.event.comment.id }}" in raw
    assert "cancel-in-progress: false" in raw
    assert "github.event.comment.body" not in raw.split("concurrency:", 1)[1].split("jobs:", 1)[0]
    assert "gh api --paginate" in raw
    assert "scripts/authorized_teams_e2e_admission.py" in raw
    dispatch = raw.split("- name: Dispatch fixed workflow on main", 1)[1]
    assert "if: steps.teams_admission.outputs.admitted != 'false'" in dispatch
    evidence = raw.split("- name: Validate exact dispatched run evidence", 1)[1]
    assert "if: steps.teams_admission.outputs.admitted != 'false'" in evidence
    assert "'duplicate_suppressed'" in raw
