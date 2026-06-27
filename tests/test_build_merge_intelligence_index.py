from __future__ import annotations

from scripts.build_merge_intelligence_index import build_index, build_lane_priority, recommendation_for, score_mergeability


def test_merge_intelligence_scores_parallel_safe_runtime_governance() -> None:
    report = {
        "risk": "low",
        "lane": "runtime-governance",
        "parallel_safe": True,
        "blocking_reasons": [],
        "changed_paths": ["docs/ops-dashboard/data/health.json"],
        "critical_files": [],
        "signals": {"workflow_change_count": 0, "concurrent_hotspot_paths": []},
    }

    score = score_mergeability(report)

    assert score >= 88
    assert recommendation_for(score, report) == "merge_imediato"


def test_merge_intelligence_blocks_missing_source_safely() -> None:
    index = build_index({}, {})

    assert index["source_available"] is False
    assert index["merge_intelligence"]["recommendation"] == "isolamento_obrigatorio"
    assert "conflict_risk_report_missing" in index["merge_intelligence"]["blocking_reasons"]


def test_merge_lane_priority_marks_current_lane() -> None:
    index = build_index(
        {
            "risk": "medium",
            "lane": "implementation",
            "parallel_safe": True,
            "blocking_reasons": [],
            "changed_paths": ["backend/app/service.py"],
            "critical_files": [],
            "signals": {"workflow_change_count": 0, "concurrent_hotspot_paths": []},
        },
        {},
    )

    priority = build_lane_priority(index)

    current = [item for item in priority["ranking"] if item["current_pr_lane"]]
    assert len(current) == 1
    assert current[0]["lane"] == "implementation"
