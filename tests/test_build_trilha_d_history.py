from __future__ import annotations

import json
from pathlib import Path

from scripts.build_trilha_d_history import (
    NEXT_INCREMENT_AFTER_PARETO_DASHBOARD,
    NEXT_INCREMENT_AFTER_PREDICTIVE_DASHBOARD,
    build_payload,
    ingest_report_into_history,
    merge_history,
    ops_dashboard_pareto_surface_ready,
    ops_dashboard_predictive_gate_surface_ready,
    report_to_history_entry,
    resolve_next_increment,
    trend_for,
)
from scripts.trilha_d_qualidade_governanca import consolidate


def dimension_fixture(
    dimension: str,
    *,
    status: str = "passed",
    score: float = 100.0,
) -> dict:
    return {
        "dimension": dimension,
        "status": status,
        "score": score,
        "duration_seconds": 1.0,
        "summary": f"{dimension} ok",
        "details": {},
        "blockers": [],
        "recommendations": [],
    }


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


def test_report_to_history_entry_maps_consolidated_report() -> None:
    report = consolidate(
        [
            dimension_fixture("tests"),
            dimension_fixture("coverage", status="failed", score=50.0),
            dimension_fixture("mutation"),
            dimension_fixture("contract"),
            dimension_fixture("schema"),
            dimension_fixture("ci-watch"),
        ],
        repository="ericson-j-santos/reqsys-v2-enterprise-real",
        run_id="999001",
    )

    entry = report_to_history_entry(report)

    assert entry["run_id"] == "999001"
    assert entry["source"] == "github_actions_artifact"
    assert entry["state"] == "failed"
    assert entry["dimensions"]["coverage"]["score"] == 50.0


def test_merge_history_deduplicates_run_id() -> None:
    existing = [{"timestamp": "t1", "run_id": "1", "state": "green", "average_score": 90.0, "dimensions": {}}]
    updated = {"timestamp": "t2", "run_id": "1", "state": "failed", "average_score": 70.0, "dimensions": {}}

    merged = merge_history(existing, updated)

    assert len(merged) == 1
    assert merged[0]["average_score"] == 70.0


def test_ingest_report_into_history_appends_sample(tmp_path: Path) -> None:
    output = tmp_path / "trilha-d-history.json"
    output.write_text(
        json.dumps(
            {
                "history": [
                    {
                        "timestamp": "2026-06-27T00:00:00Z",
                        "run_id": "old",
                        "state": "green",
                        "average_score": 95.0,
                        "dimensions": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.json"
    report = consolidate(
        [
            dimension_fixture("tests"),
            dimension_fixture("coverage"),
            dimension_fixture("mutation"),
            dimension_fixture("contract"),
            dimension_fixture("schema"),
            dimension_fixture("ci-watch"),
        ],
        repository="ericson-j-santos/reqsys-v2-enterprise-real",
        run_id="run-ingest-1",
    )
    report_path.write_text(json.dumps(report), encoding="utf-8")

    payload = ingest_report_into_history(str(report_path), str(output))

    assert payload["summary"]["artifact_ingestion_enabled"] is True
    assert payload["runtime_dashboard_contract"]["refresh_strategy"] == "artifact_ingestion_on_trilha_d_consolidate"
    assert payload["summary"]["next_increment"] == NEXT_INCREMENT_AFTER_PREDICTIVE_DASHBOARD
    assert len(payload["history"]) == 2
    assert payload["history"][-1]["run_id"] == "run-ingest-1"


def test_resolve_next_increment_advances_after_pareto_dashboard_surface() -> None:
    assert ops_dashboard_pareto_surface_ready() is True
    assert resolve_next_increment(artifact_ingestion=True) == NEXT_INCREMENT_AFTER_PREDICTIVE_DASHBOARD
    assert resolve_next_increment(artifact_ingestion=False) == "artifact_ingestion_refresh"


def test_resolve_next_increment_advances_after_predictive_gate_surface() -> None:
    assert ops_dashboard_predictive_gate_surface_ready() is True
    assert resolve_next_increment(artifact_ingestion=True) == NEXT_INCREMENT_AFTER_PREDICTIVE_DASHBOARD
