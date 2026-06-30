from __future__ import annotations

import json
from pathlib import Path

from scripts.build_trilha_d_history import (
    NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION,
    NEXT_INCREMENT_AFTER_CONTINUOUS_MONITORING,
    NEXT_INCREMENT_AFTER_COVERAGE_TARGETED,
    NEXT_INCREMENT_AFTER_GOVERNANCE_DEEP_LINKS,
    NEXT_INCREMENT_AFTER_INGESTION,
    NEXT_INCREMENT_AFTER_PARETO_DASHBOARD,
    NEXT_INCREMENT_AFTER_PREDICTIVE_DASHBOARD,
    NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION_REFRESH,
    NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD,
    artifact_ingestion_refresh_surface_ready,
    artifact_ingestion_surface_ready,
    build_payload,
    continuous_trilha_d_monitoring_surface_ready,
    coverage_targeted_critical_paths_ready,
    coverage_targeted_surface_ready,
    governance_deep_links_surface_ready,
    governance_workflow_deep_links_surface_ready,
    ingest_report_into_history,
    merge_history,
    merge_readiness_history_surface_ready,
    ops_dashboard_pareto_surface_ready,
    ops_dashboard_predictive_gate_surface_ready,
    report_to_history_entry,
    resolve_next_increment,
    trilha_d_history_dashboard_surface_ready,
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
    assert "workflow_run_url" in payload["runtime_dashboard_contract"]["series_fields"]
    assert payload["history"][0]["workflow_run_url"]


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
    assert payload["runtime_dashboard_contract"]["refresh_strategy"] in {
        "artifact_ingestion_on_trilha_d_consolidate",
        "workflow_runs_deep_links_enabled",
    }
    assert payload["summary"]["next_increment"] in {
        NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION,
        NEXT_INCREMENT_AFTER_CONTINUOUS_MONITORING,
        NEXT_INCREMENT_AFTER_COVERAGE_TARGETED,
        NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD,
    }
    assert len(payload["history"]) == 2
    assert payload["history"][-1]["run_id"] == "run-ingest-1"
    assert payload["history"][-1]["workflow_run_url"]


def test_resolve_next_increment_when_pipeline_completo() -> None:
    assert ops_dashboard_pareto_surface_ready() is True
    assert ops_dashboard_predictive_gate_surface_ready() is True
    assert coverage_targeted_critical_paths_ready() is True
    assert governance_deep_links_surface_ready() is True
    assert trilha_d_history_dashboard_surface_ready() is True
    assert resolve_next_increment(artifact_ingestion=False) == NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD


def test_artifact_ingestion_refresh_surface_ready_detecta_arquivos() -> None:
    assert artifact_ingestion_refresh_surface_ready() is True


def test_resolve_next_increment_when_artifact_ingestion_habilitado() -> None:
    assert artifact_ingestion_surface_ready() is True
    expected = resolve_next_increment(artifact_ingestion=True)
    if merge_readiness_history_surface_ready() and artifact_ingestion_refresh_surface_ready():
        assert expected == NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION
    elif merge_readiness_history_surface_ready():
        assert expected == NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD
    elif governance_workflow_deep_links_surface_ready() and coverage_targeted_surface_ready():
        assert expected == NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION_REFRESH
    elif coverage_targeted_surface_ready():
        assert expected == NEXT_INCREMENT_AFTER_COVERAGE_TARGETED
    elif continuous_trilha_d_monitoring_surface_ready():
        assert expected == NEXT_INCREMENT_AFTER_CONTINUOUS_MONITORING
    else:
        assert expected == NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION


def test_merge_readiness_history_surface_ready_detecta_arquivos() -> None:
    assert merge_readiness_history_surface_ready() is True


def test_resolve_next_increment_quando_merge_readiness_pendente(monkeypatch) -> None:
    monkeypatch.setattr("scripts.build_trilha_d_history.merge_readiness_history_surface_ready", lambda repo_root=None: False)
    assert resolve_next_increment(artifact_ingestion=True) == NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION_REFRESH


def test_resolve_next_increment_when_continuous_monitoring_habilitado() -> None:
    assert continuous_trilha_d_monitoring_surface_ready() is True
    expected = resolve_next_increment(artifact_ingestion=True)
    if merge_readiness_history_surface_ready() and artifact_ingestion_refresh_surface_ready():
        assert expected == NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION
    elif merge_readiness_history_surface_ready():
        assert expected == NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD
    elif governance_workflow_deep_links_surface_ready() and coverage_targeted_surface_ready():
        assert expected == NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION_REFRESH
    elif coverage_targeted_surface_ready():
        assert expected == NEXT_INCREMENT_AFTER_COVERAGE_TARGETED
    else:
        assert expected == NEXT_INCREMENT_AFTER_CONTINUOUS_MONITORING


def test_coverage_targeted_surface_ready_detecta_arquivos_e_workflow() -> None:
    assert coverage_targeted_critical_paths_ready() is True
    assert coverage_targeted_surface_ready() is True


def test_resolve_next_increment_when_governance_pendente(monkeypatch) -> None:
    monkeypatch.setattr("scripts.build_trilha_d_history.trilha_d_history_dashboard_surface_ready", lambda repo_root=None: False)
    monkeypatch.setattr("scripts.build_trilha_d_history.governance_workflow_deep_links_surface_ready", lambda repo_root=None: False)
    assert resolve_next_increment(artifact_ingestion=True) == NEXT_INCREMENT_AFTER_COVERAGE_TARGETED


def test_resolve_next_increment_when_pareto_pendente(monkeypatch) -> None:
    monkeypatch.setattr("scripts.build_trilha_d_history.ops_dashboard_pareto_surface_ready", lambda repo_root=None: False)
    assert resolve_next_increment(artifact_ingestion=True) == NEXT_INCREMENT_AFTER_INGESTION


def test_resolve_next_increment_when_trilha_d_dashboard_pendente(monkeypatch) -> None:
    monkeypatch.setattr("scripts.build_trilha_d_history.governance_workflow_deep_links_surface_ready", lambda repo_root=None: True)
    monkeypatch.setattr("scripts.build_trilha_d_history.trilha_d_history_dashboard_surface_ready", lambda repo_root=None: False)
    assert resolve_next_increment(artifact_ingestion=True) == NEXT_INCREMENT_AFTER_GOVERNANCE_DEEP_LINKS


def test_resolve_next_increment_advances_after_predictive_gate_surface(monkeypatch) -> None:
    monkeypatch.setattr("scripts.build_trilha_d_history.ops_dashboard_pareto_surface_ready", lambda repo_root=None: True)
    monkeypatch.setattr("scripts.build_trilha_d_history.ops_dashboard_predictive_gate_surface_ready", lambda repo_root=None: False)
    assert resolve_next_increment(artifact_ingestion=True) == NEXT_INCREMENT_AFTER_PARETO_DASHBOARD


def test_coverage_targeted_critical_paths_ready_detects_required_files() -> None:
    assert coverage_targeted_critical_paths_ready() is True
