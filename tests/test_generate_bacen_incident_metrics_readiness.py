import json
from datetime import UTC, datetime

import pytest

from scripts.generate_bacen_incident_metrics_readiness import build_readiness


def _metrics(**overrides):
    document = {
        "schema_version": "1.0.0",
        "control_id": "BACEN-03",
        "period_start": "2026-04-01T00:00:00+00:00",
        "period_end": "2026-06-30T23:59:59+00:00",
        "total_incidents": 4,
        "sla_met_incidents": 3,
        "mean_time_to_detect_minutes": 12.5,
        "mean_time_to_recover_minutes": 78,
        "open_corrective_actions": 2,
        "overdue_corrective_actions": 0,
        "source_reference": "artifacts/incidents/quarterly-metrics.json",
        "human_reviewed": False,
    }
    document.update(overrides)
    return document


def test_missing_metrics_stays_advisory(tmp_path):
    output = tmp_path / "readiness.json"

    report = build_readiness(
        tmp_path / "missing.json",
        output,
        datetime(2026, 7, 30, tzinfo=UTC),
    )

    assert report["state"] == "pending_real_metrics"
    assert report["result"] == "advisory"
    assert report["metrics_present"] is False
    assert report["production_touched"] is False


def test_valid_metrics_wait_for_human_review(tmp_path):
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps(_metrics()), encoding="utf-8")

    report = build_readiness(
        metrics,
        tmp_path / "readiness.json",
        datetime(2026, 7, 30, tzinfo=UTC),
    )

    assert report["state"] == "metrics_ready_pending_human_review"
    assert report["sla_rate_percent"] == 75.0
    assert report["result"] == "advisory"
    assert report["human_reviewed"] is False


def test_human_reviewed_metrics_are_ready(tmp_path):
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(_metrics(human_reviewed=True, total_incidents=0, sla_met_incidents=0)),
        encoding="utf-8",
    )

    report = build_readiness(metrics, tmp_path / "readiness.json")

    assert report["state"] == "metrics_ready"
    assert report["result"] == "passed"
    assert report["sla_rate_percent"] == 100.0


def test_inconsistent_metrics_are_rejected(tmp_path):
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(_metrics(total_incidents=1, sla_met_incidents=2)),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sla_met_incidents"):
        build_readiness(metrics, tmp_path / "readiness.json")
