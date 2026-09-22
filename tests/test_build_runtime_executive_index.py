from __future__ import annotations

from scripts.build_runtime_executive_index import build_runtime_executive_index


def test_runtime_executive_index_consolidates_public_cards() -> None:
    health = {
        "repo": "example/repo",
        "overall_status": "passed",
        "health_score": 100,
        "critical_failure_count": 0,
        "warning_count": 0,
        "public_runtime_readiness": {
            "available": True,
            "operational_status": "passed",
            "readiness_percent": 95,
            "base_url": "https://reqsys-api.fly.dev",
            "dashboard_ready": True,
            "login_ready": True,
            "api_ready": True,
            "runtime_ready": True,
            "evidence_ready": True,
            "blocking_issues": [],
        },
        "delivery_finalization": {
            "available": True,
            "status": "passed",
            "final_score": 99.5,
            "residual_gap": 0.5,
            "indicator_count": 4,
            "passed_indicator_count": 4,
        },
        "checks": [
            {"name": "PR Evidence Gate", "status": "passed", "domain": "evidence_gate"},
        ],
    }
    merge_index = {
        "repo": "example/repo",
        "source_available": True,
        "merge_intelligence": {
            "risk": "low",
            "lane": "runtime-governance",
            "parallel_safe": True,
            "mergeability_score": 88,
            "recommendation": "merge_imediato",
            "queue_saturation": "low",
            "queue_pressure": 1,
            "confidence": "medium",
            "blocking_reasons": [],
        },
        "hotspot_heatmap": [{"path": "docs/ops-dashboard/index.html"}],
    }
    lane_priority = {
        "ranking": [
            {"lane": "runtime-governance", "priority_score": 90, "parallelism": "safe", "current_pr_lane": True},
            {"lane": "implementation", "priority_score": 50, "parallelism": "serial", "current_pr_lane": False},
        ]
    }

    payload = build_runtime_executive_index(health, merge_index, lane_priority)

    assert payload["schema_version"] == "1.1.0"
    assert payload["repo"] == "example/repo"
    assert payload["summary"]["status"] == "passed"
    assert payload["summary"]["risk"] == "low"
    assert payload["cards"]["health"]["score"] == 100
    assert payload["cards"]["readiness"]["readiness_percent"] == 95
    assert payload["cards"]["merge_intelligence"]["mergeability_score"] == 88
    assert payload["cards"]["merge_intelligence"]["safe_lane_count"] == 1
    assert payload["cards"]["evidence_gate"]["status"] == "passed"
    assert payload["cards"]["finalization"]["final_score"] == 99.5
    assert "runtime_executive_index" in payload["links"]


def test_runtime_executive_index_uses_real_artifacts_when_available() -> None:
    health = {
        "repo": "example/repo",
        "overall_status": "passed",
        "health_score": 90,
        "public_runtime_readiness": {
            "available": True,
            "operational_status": "passed",
            "readiness_percent": 90,
            "blocking_issues": [],
        },
        "checks": [],
    }
    merge_index = {
        "repo": "example/repo",
        "source_available": False,
        "merge_intelligence": {
            "queue_saturation": "low",
            "queue_pressure": 1,
            "confidence": "medium",
        },
        "hotspot_heatmap": [],
    }
    lane_priority = {"ranking": [{"lane": "runtime-governance", "parallelism": "safe"}]}
    evidence_gate = {
        "gate": {
            "status": "passed",
            "failures": [],
            "required_workflows": [
                {"name": "CI", "successful_runs": 1},
                {"name": "Governance", "successful_runs": 1},
            ],
            "observed_artifacts": [{"name": "pr-evidence-gate"}],
        }
    }
    finalization = {
        "status": "passed",
        "final_score": 98,
        "residual_gap": 2,
        "indicators": [
            {"name": "readiness", "status": "passed"},
            {"name": "evidence", "status": "passed"},
        ],
    }
    conflict_report = {
        "risk": "low",
        "lane": "runtime-governance",
        "parallel_safe": True,
        "recommendation": "merge_paralelo_seguro",
        "blocking_reasons": [],
        "critical_files": [],
    }

    payload = build_runtime_executive_index(
        health,
        merge_index,
        lane_priority,
        evidence_gate_report=evidence_gate,
        finalization_report=finalization,
        conflict_risk_report=conflict_report,
    )

    assert payload["cards"]["evidence_gate"]["available"] is True
    assert payload["cards"]["evidence_gate"]["source_artifact"] == "pr-evidence-gate"
    assert payload["cards"]["evidence_gate"]["required_workflow_count"] == 2
    assert payload["cards"]["finalization"]["available"] is True
    assert payload["cards"]["finalization"]["final_score"] == 98
    assert payload["cards"]["merge_intelligence"]["available"] is True
    assert payload["cards"]["merge_intelligence"]["source_artifacts"]["conflict_risk_report"] is True
    assert payload["cards"]["merge_intelligence"]["parallel_safe"] is True
    assert "real_artifact_precedence_when_available" in payload["guardrails"]


def test_runtime_executive_index_fallback_marks_risk_when_artifacts_missing() -> None:
    payload = build_runtime_executive_index({}, {}, {})

    assert payload["repo"] == "unknown"
    assert payload["summary"]["status"] == "warning"
    assert payload["cards"]["readiness"]["available"] is False
    assert payload["cards"]["merge_intelligence"]["available"] is False
    assert payload["cards"]["evidence_gate"]["available"] is False
    assert "safe_fallback_when_source_artifact_missing" in payload["guardrails"]
