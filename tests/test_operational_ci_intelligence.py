from pathlib import Path
import json
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ci_intelligence_lib import (  # noqa: E402
    build_instability_snapshot,
    build_pareto_ranking,
    calculate_instability_trend,
    classify_text,
    compute_instability_rate,
    merge_instability_history,
)
from scripts.operational_ci_intelligence import build_report, build_rerun_assessment  # noqa: E402


SAMPLE_KB = {
    "rerun_policy": {"max_reruns_without_commit_change": 2},
    "known_failures": [
        {
            "id": "OCI-ARTIFACT-001",
            "category": "artifact",
            "severity": "medium",
            "owner": "ci_cd",
            "symptoms": ["Artifact not found"],
            "safe_rerun": True,
        },
        {
            "id": "OCI-TEST-001",
            "category": "test_failure",
            "severity": "high",
            "owner": "backend",
            "symptoms": ["pytest failed"],
            "safe_rerun": False,
        },
    ],
}

SAMPLE_CATALOG = {
    "patterns": [
        {
            "id": "FPE-GH-PERM-001",
            "name": "Permission denied",
            "category": "permissions",
            "severity": "high",
            "match_any": ["Resource not accessible by integration"],
            "can_auto_rerun": False,
        }
    ]
}


def run(conclusion: str, text: str = "", workflow: str = "CI") -> dict:
    return {
        "databaseId": 1,
        "workflowName": workflow,
        "status": "completed",
        "conclusion": conclusion,
        "headSha": "abc123",
        "name": workflow,
        **({"jobs": [{"log_excerpt": text}]} if text else {}),
    }


def test_classify_text_merges_kb_and_patterns() -> None:
    text = "Artifact not found and Resource not accessible by integration"
    matches = classify_text(text, SAMPLE_KB, SAMPLE_CATALOG)

    assert len(matches) == 2
    sources = {match["source"] for match in matches}
    assert sources == {"knowledge_base", "failure_pattern_engine"}


def test_build_pareto_ranking_orders_by_impact() -> None:
    classified = [
        {
            "run_id": 1,
            "matches": [
                {"id": "A", "category": "artifact", "severity": "medium", "name": "Artifact", "source": "knowledge_base"},
                {"id": "B", "category": "test_failure", "severity": "high", "name": "Test", "source": "knowledge_base"},
            ],
        },
        {
            "run_id": 2,
            "matches": [
                {"id": "B", "category": "test_failure", "severity": "high", "name": "Test", "source": "knowledge_base"},
            ],
        },
    ]
    pareto = build_pareto_ranking(classified)

    assert pareto["total_causes"] == 2
    assert pareto["top_causes"][0]["id"] == "B"
    assert pareto["top_causes"][0]["occurrences"] == 2
    assert pareto["top_causes"][0]["pareto_tier"] == "A"


def test_compute_instability_rate() -> None:
    runs = [run("success"), run("failure"), run("cancelled")]
    rate = compute_instability_rate(runs)

    assert rate["total"] == 3
    assert rate["failed"] == 1
    assert rate["cancelled"] == 1
    assert rate["rate_percent"] == 66.67


def test_instability_history_trend_improving() -> None:
    history = [
        {"snapshot_at_utc": "2026-06-01T00:00:00+00:00", "instability_rate_percent": 50.0, "operational_score": 60},
        {"snapshot_at_utc": "2026-06-02T00:00:00+00:00", "instability_rate_percent": 20.0, "operational_score": 85},
    ]
    trend = calculate_instability_trend(history)

    assert trend["direction"] == "melhorando"
    assert trend["delta_instability"] == -30.0
    assert trend["delta_score"] == 25.0


def test_build_report_includes_pareto_and_history(tmp_path: Path) -> None:
    runs = [
        run("failure", "Artifact not found", "Evidence Gate"),
        run("failure", "pytest failed", "Backend Tests"),
        run("success"),
    ]
    report = build_report(runs, SAMPLE_KB, catalog=SAMPLE_CATALOG, history=[])

    assert report["schema_version"] == "1.1.0"
    assert "pareto_failures" in report
    assert report["pareto_failures"]["total_causes"] >= 1
    assert "instability_history" in report
    assert report["instability_history"]["points"] == 1
    assert report["instability"]["rate_percent"] == 66.67
    assert any("Pareto tier A" in action for action in report["recommended_next_actions"])


def test_merge_instability_history_respects_max_items() -> None:
    existing = [{"snapshot_at_utc": f"2026-06-0{i}T00:00:00+00:00"} for i in range(1, 5)]
    snapshot = {"snapshot_at_utc": "2026-06-10T00:00:00+00:00"}
    merged = merge_instability_history(existing, snapshot, max_items=3)

    assert len(merged) == 3
    assert merged[-1]["snapshot_at_utc"] == "2026-06-10T00:00:00+00:00"


def test_build_rerun_assessment_detects_loop() -> None:
    runs = [
        {"workflowName": "CI", "headSha": "same", "conclusion": "failure"},
        {"workflowName": "CI", "headSha": "same", "conclusion": "failure"},
        {"workflowName": "CI", "headSha": "same", "conclusion": "failure"},
    ]
    assessment = build_rerun_assessment(runs, SAMPLE_KB)

    assert assessment["blocked"] is True
    assert len(assessment["loops_detected"]) == 1
