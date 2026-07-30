import json
from datetime import UTC, datetime, timedelta

import pytest

from scripts.generate_bacen_restore_trend_readiness import build_trend


def _write_evidence(
    path,
    *,
    completed_at,
    rto_seconds=30.0,
    rpo_minutes=5,
    result="passed",
    evidence_class="isolated_stg_restore_test",
    production_touched=False,
):
    path.write_text(
        json.dumps(
            {
                "schema_version": "2.0.1",
                "control_id": "BACEN-04",
                "evidence_class": evidence_class,
                "production_restore_claimed": False,
                "production_touched": production_touched,
                "restore_completed_at": completed_at.isoformat(),
                "rpo_minutes": rpo_minutes,
                "rto_seconds": rto_seconds,
                "rpo_target_minutes": 1440,
                "rto_target_seconds": 14400,
                "result": result,
            }
        ),
        encoding="utf-8",
    )


def test_empty_history_is_advisory(tmp_path):
    report = build_trend(
        str(tmp_path / "bacen-04-*.json"),
        tmp_path / "trend.json",
        datetime(2026, 7, 30, tzinfo=UTC),
    )

    assert report["state"] == "pending_operational_history"
    assert report["sample_count"] == 0
    assert report["production_touched"] is False


def test_two_samples_are_insufficient(tmp_path):
    now = datetime(2026, 7, 30, tzinfo=UTC)
    for index in range(2):
        _write_evidence(
            tmp_path / f"bacen-04-{index}.json",
            completed_at=now - timedelta(days=index + 1),
        )

    report = build_trend(str(tmp_path / "bacen-04-*.json"), tmp_path / "trend.json", now)

    assert report["state"] == "insufficient_operational_history"
    assert report["sample_count"] == 2
    assert report["pass_rate_percent"] == 100.0


def test_three_fresh_passing_samples_form_ready_trend(tmp_path):
    now = datetime(2026, 7, 30, tzinfo=UTC)
    for index, rto in enumerate((20.0, 30.0, 40.0)):
        _write_evidence(
            tmp_path / f"bacen-04-{index}.json",
            completed_at=now - timedelta(days=index + 1),
            rto_seconds=rto,
        )

    report = build_trend(str(tmp_path / "bacen-04-*.json"), tmp_path / "trend.json", now)

    assert report["state"] == "trend_ready"
    assert report["result"] == "passed"
    assert report["median_rto_seconds"] == 30.0
    assert report["p95_rto_seconds"] == 40.0


def test_production_touch_claim_is_rejected(tmp_path):
    now = datetime(2026, 7, 30, tzinfo=UTC)
    _write_evidence(
        tmp_path / "bacen-04-invalid.json",
        completed_at=now,
        production_touched=True,
    )

    with pytest.raises(ValueError, match="production_touched"):
        build_trend(str(tmp_path / "bacen-04-*.json"), tmp_path / "trend.json", now)
