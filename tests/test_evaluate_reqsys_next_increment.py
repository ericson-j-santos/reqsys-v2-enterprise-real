from scripts.evaluate_reqsys_next_increment import build_report


def test_prioritizes_failed_required_workflow():
    runs = [
        {"name": "CI — ReqSys v2 Enterprise", "status": "completed", "conclusion": "failure", "created_at": "2026-07-21T10:00:00Z"},
        {"name": "PR Evidence Gate", "status": "completed", "conclusion": "success", "created_at": "2026-07-21T10:00:00Z"},
    ]
    report = build_report([], runs, {"status": "READY", "metric_coverage_percent": 100}, {"snapshots": [{}, {}]})
    assert report["status"] == "ACTION_REQUIRED"
    assert report["next_safe_increment"] == "remediate_failed_required_workflows"
    assert "required_workflow_failure" in report["human_blockers"]
    assert report["production_ready"] is False


def test_requires_history_before_eta_consolidation():
    names = [
        "CI — ReqSys v2 Enterprise",
        "PR Evidence Gate",
        "Governed Merge Queue",
        "Security Baseline Gate",
        "Security Specialized Scanners",
        "Instrumented Executive Readiness",
    ]
    runs = [
        {"name": name, "status": "completed", "conclusion": "success", "created_at": "2026-07-21T10:00:00Z"}
        for name in names
    ]
    report = build_report([], runs, {"status": "READY", "metric_coverage_percent": 100}, {"snapshots": [{}]})
    assert report["validated"] is True
    assert report["consolidated"] is False
    assert report["next_safe_increment"] == "accumulate_instrumented_history"


def test_ready_for_human_decision_with_complete_evidence():
    names = [
        "CI — ReqSys v2 Enterprise",
        "PR Evidence Gate",
        "Governed Merge Queue",
        "Security Baseline Gate",
        "Security Specialized Scanners",
        "Instrumented Executive Readiness",
    ]
    runs = [
        {"name": name, "status": "completed", "conclusion": "success", "created_at": "2026-07-21T10:00:00Z"}
        for name in names
    ]
    report = build_report([], runs, {"status": "READY", "metric_coverage_percent": 100}, {"snapshots": [{}, {}], "eta": {"production": {"state": "achieved"}}})
    assert report["status"] == "READY_FOR_HUMAN_DECISION"
    assert report["production_ready"] is True
    assert report["human_approval_required"] is True
    assert report["automatic_promotion_allowed"] is False
