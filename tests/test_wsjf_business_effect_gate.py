from datetime import datetime, timedelta, timezone

from scripts.wsjf_business_effect_gate import evaluate


def _valid(now):
    return {
        "environment": "dev",
        "real": True,
        "mocked": False,
        "planner_task_id": "task-real-001",
        "excel_task_id": "task-real-001",
        "excel_matching_rows": 1,
        "local_fields_preserved": True,
        "planner_writeback_detected": False,
        "source_run_url": "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/1",
        "captured_at": now.isoformat(),
    }


def test_business_effect_real_passes():
    now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    result = evaluate(_valid(now), now=now)
    assert result["status"] == "passed"
    assert result["blocking_issues"] == []


def test_duplicate_excel_row_blocks_acceptance():
    now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    data = _valid(now)
    data["excel_matching_rows"] = 2
    result = evaluate(data, now=now)
    assert "excel_row_must_be_unique" in result["blocking_issues"]


def test_local_fields_must_be_preserved():
    now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    data = _valid(now)
    data["local_fields_preserved"] = False
    result = evaluate(data, now=now)
    assert "local_fields_not_proven_preserved" in result["blocking_issues"]


def test_mocked_evidence_is_rejected():
    now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    data = _valid(now)
    data["mocked"] = True
    result = evaluate(data, now=now)
    assert "mocked_evidence_forbidden" in result["blocking_issues"]


def test_stale_evidence_is_rejected():
    now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    data = _valid(now - timedelta(hours=25))
    result = evaluate(data, now=now, max_age_hours=24)
    assert "evidence_stale" in result["blocking_issues"]
