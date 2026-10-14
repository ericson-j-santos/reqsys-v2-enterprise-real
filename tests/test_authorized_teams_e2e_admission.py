"""No-external-effects tests for the authorized Teams E2E admission gate."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.authorized_teams_e2e_admission import (
    AdmissionError, COMMAND, WORKER_CANARY_COMMAND, WORKER_RESTORE_COMMAND, DEV_DEPLOY_CHECK_COMMAND, decide,
)

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


def _record(comment_id: int, seconds: int, *, user: str = "ericson-j-santos"):
    return {"id": comment_id, "created_at": _instant(seconds), "user_login": user}


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


def test_worker_canary_duplicate_and_reverse_gateway_order():
    comments = [_record(100, 0), _record(101, 18)]
    later = decide(_event(101, 18, command=WORKER_CANARY_COMMAND), comments,
                   expected_sha=SHA, command=WORKER_CANARY_COMMAND)
    earlier = decide(_event(100, command=WORKER_CANARY_COMMAND), comments,
                     expected_sha=SHA, command=WORKER_CANARY_COMMAND)
    assert earlier["admitted"] is True
    assert later["admitted"] is False
    assert later["canonical_comment_id"] == 100
    assert later["expected_sha"] == SHA


def test_worker_canary_cooldown_and_invalid_cases():
    outcome = decide(_event(102, 121, command=WORKER_CANARY_COMMAND),
                     [_record(100, 0), _record(102, 121)],
                     expected_sha=SHA, command=WORKER_CANARY_COMMAND)
    assert outcome["admitted"] is True
    with pytest.raises(AdmissionError, match="command_not_allowlisted"):
        decide(_event(100), [_record(100, 0)],
               expected_sha=SHA, command=WORKER_CANARY_COMMAND)
    with pytest.raises(AdmissionError, match="physical_command_not_allowlisted"):
        decide(_event(100), [_record(100, 0)],
               expected_sha=SHA, command="/reqsys run arbitrary")
    with pytest.raises(AdmissionError, match="current_comment_not_uniquely_read_back"):
        decide(_event(101, 18, command=WORKER_CANARY_COMMAND),
               [_record(100, 0)], expected_sha=SHA, command=WORKER_CANARY_COMMAND)


def test_worker_canary_gateway_dispatched_once_after_admission():
    raw = WORKFLOW.read_text(encoding="utf-8")
    gate = "if: steps.route.outputs.target == 'pc24x7-teams-ephemeral-e2e.yml' || steps.route.outputs.mode == 'candidate-canary' || steps.route.outputs.mode == 'restore-rehearsal' || steps.route.outputs.mode == 'deploy-check'"
    assert raw.count(gate) == 2
    assert '--command "$COMMAND"' in raw
    assert 'physical_command_not_allowlisted' in raw
    assert 'if: steps.teams_admission.outputs.admitted != ' + "'false'" in raw
    assert 'group: reqsys-authorized-actions-gateway-' in raw


def test_nonowner_comment_record_cannot_suppress_authorized_dispatch():
    with pytest.raises(AdmissionError, match="comment_record_author_invalid"):
        decide(_event(101, 18, command=WORKER_CANARY_COMMAND),
               [_record(100, 0, user="intruder"), _record(101, 18)],
               expected_sha=SHA, command=WORKER_CANARY_COMMAND)
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert raw.count('.user.login == "ericson-j-santos"') >= 2
    assert raw.count('user_login: .user.login') >= 2


def test_real_restore_admission_positive_duplicate_and_negative_controls():
    """Regression: the workflow and parser must share the exact fixed command."""
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert f"github.event.comment.body == '{WORKER_RESTORE_COMMAND}'" in raw
    assert f"'{WORKER_RESTORE_COMMAND}')" in raw
    assert '--command "$COMMAND"' in raw
    assert "steps.route.outputs.mode == 'restore-rehearsal'" in raw

    comments = [_record(400, 0), _record(401, 2)]
    first = decide(_event(400, command=WORKER_RESTORE_COMMAND), comments,
                   expected_sha=SHA, command=WORKER_RESTORE_COMMAND)
    duplicate = decide(_event(401, 2, command=WORKER_RESTORE_COMMAND), comments,
                       expected_sha=SHA, command=WORKER_RESTORE_COMMAND)
    assert first["admitted"] is True
    assert duplicate["admitted"] is False
    assert duplicate["canonical_comment_id"] == 400
    assert decide(_event(402, 121, command=WORKER_RESTORE_COMMAND),
                  [_record(400, 0), _record(402, 121)],
                  expected_sha=SHA, command=WORKER_RESTORE_COMMAND)["admitted"] is True
    with pytest.raises(AdmissionError, match="command_not_allowlisted"):
        decide(_event(400, command=WORKER_CANARY_COMMAND), [_record(400, 0)],
               expected_sha=SHA, command=WORKER_RESTORE_COMMAND)
    with pytest.raises(AdmissionError, match="physical_command_not_allowlisted"):
        decide(_event(400, command="/reqsys run arbitrary"), [_record(400, 0)],
               expected_sha=SHA, command="/reqsys run arbitrary")


def test_dev_deploy_check_admits_one_and_suppresses_replay():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.comment.body == '" + DEV_DEPLOY_CHECK_COMMAND + "'" in raw
    assert "'" + DEV_DEPLOY_CHECK_COMMAND + "')" in raw
    assert "-f mode=deploy-check" in raw
    comments = [_record(700, 0), _record(701, 6)]
    first = decide(_event(700, command=DEV_DEPLOY_CHECK_COMMAND), comments,
                   expected_sha=SHA, command=DEV_DEPLOY_CHECK_COMMAND)
    replay = decide(_event(701, 6, command=DEV_DEPLOY_CHECK_COMMAND), comments,
                    expected_sha=SHA, command=DEV_DEPLOY_CHECK_COMMAND)
    assert first["admitted"] is True
    assert replay["admitted"] is False and replay["canonical_comment_id"] == 700
    later = decide(_event(702, 121, command=DEV_DEPLOY_CHECK_COMMAND),
                   [_record(700, 0), _record(702, 121)],
                   expected_sha=SHA, command=DEV_DEPLOY_CHECK_COMMAND)
    assert later["admitted"] is True


def test_dev_deploy_check_rejects_wrong_command_and_incomplete_readback():
    with pytest.raises(AdmissionError, match="command_not_allowlisted"):
        decide(_event(700, command=COMMAND), [_record(700, 0)],
               expected_sha=SHA, command=DEV_DEPLOY_CHECK_COMMAND)
    with pytest.raises(AdmissionError, match="current_comment_not_uniquely_read_back"):
        decide(_event(701, 6, command=DEV_DEPLOY_CHECK_COMMAND),
               [_record(700, 0)], expected_sha=SHA, command=DEV_DEPLOY_CHECK_COMMAND)
