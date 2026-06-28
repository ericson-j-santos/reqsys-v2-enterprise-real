from __future__ import annotations

from scripts.build_trilha_d_history import build_payload, trend_for


def test_trend_for_detects_improving_stable_and_regressing() -> None:
    assert trend_for([88.33, 95.88]) == "improving"
    assert trend_for([95.0, 95.5]) == "stable"
    assert trend_for([95.0, 90.0]) == "regressing"


def test_build_payload_tracks_coverage_improvement() -> None:
    payload = build_payload()

    assert payload["state"] == "green"
    assert payload["trend"] == "improving"
    assert payload["summary"]["samples"] == 3
    assert payload["dimension_summary"]["coverage"]["trend"] == "improving"
    assert payload["dimension_summary"]["coverage"]["delta_from_baseline"] == 45.29
    assert payload["runtime_dashboard_contract"]["series_fields"] == ["timestamp", "average_score", "state"]


def test_build_payload_accepts_custom_history_regression() -> None:
    payload = build_payload(
        [
            {
                "timestamp": "2026-06-28T00:00:00Z",
                "state": "green",
                "average_score": 95.0,
                "dimensions": {"coverage": {"status": "passed", "score": 80.0}},
            },
            {
                "timestamp": "2026-06-28T01:00:00Z",
                "state": "failed",
                "average_score": 90.0,
                "dimensions": {"coverage": {"status": "failed", "score": 70.0}},
            },
        ]
    )

    assert payload["trend"] == "regressing"
    assert payload["dimension_summary"]["coverage"]["trend"] == "regressing"
