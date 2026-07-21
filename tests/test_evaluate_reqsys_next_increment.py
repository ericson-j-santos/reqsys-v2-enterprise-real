from scripts.evaluate_reqsys_next_increment import build_report


NAMES = [
    "CI — ReqSys v2 Enterprise",
    "PR Evidence Gate",
    "Governed Merge Queue",
    "Security Baseline Gate",
    "Security Specialized Scanners",
    "Instrumented Executive Readiness",
]


def successful_runs():
    return [
        {"name": name, "status": "completed", "conclusion": "success", "created_at": "2026-07-21T10:00:00Z"}
        for name in NAMES
    ]


def healthy_runtime():
    return {
        "endpoints": [
            {"name": "health", "ok": True, "http_code": 200, "latency_ms": 100},
            {"name": "readiness", "ok": True, "http_code": 200, "latency_ms": 120},
        ]
    }


def test_prioritizes_failed_required_workflow():
    runs = successful_runs()
    runs[0]["conclusion"] = "failure"
    report = build_report([], runs, {"status": "READY", "metric_coverage_percent": 100}, {"snapshots": [{}, {}]}, healthy_runtime())
    assert report["status"] == "ACTION_REQUIRED"
    assert report["next_safe_increment"] == "remediate_failed_required_workflows"
    assert "required_workflow_failure" in report["human_blockers"]
    assert report["production_ready"] is False


def test_runtime_smoke_is_required_before_consolidation():
    report = build_report([], successful_runs(), {"status": "READY", "metric_coverage_percent": 100}, {"snapshots": [{}, {}, {}, {}, {}]}, {})
    assert report["production_ready"] is False
    assert report["next_safe_increment"] == "restore_runtime_and_smoke_evidence"
    assert "runtime_smoke_missing" in report["human_blockers"]


def test_requires_five_history_points_for_maturity():
    report = build_report([], successful_runs(), {"status": "READY", "metric_coverage_percent": 100}, {"snapshots": [{}, {}]}, healthy_runtime())
    assert report["validated"] is True
    assert report["consolidated"] is False
    assert report["next_safe_increment"] == "accumulate_instrumented_history"


def test_incorporates_throughput_lead_time_and_runtime_metrics():
    merged_prs = [
        {"created_at": "2026-07-20T10:00:00Z", "merged_at": "2026-07-21T10:00:00Z"},
        {"created_at": "2026-07-19T10:00:00Z", "merged_at": "2026-07-21T10:00:00Z"},
    ]
    history = {
        "snapshots": [
            {"operational_readiness_percent": 80},
            {}, {}, {},
            {"operational_readiness_percent": 90},
        ],
        "eta": {"production": {"state": "projected", "days": 2}},
    }
    report = build_report([], successful_runs(), {"status": "READY", "metric_coverage_percent": 100}, history, healthy_runtime(), merged_prs)
    assert report["runtime"]["smoke_success_percent"] == 100.0
    assert report["runtime"]["average_latency_ms"] == 110.0
    assert report["integration"]["median_merge_lead_time_hours"] == 36.0
    assert report["instrumented_metrics"]["trend_delta_percent"] == 10.0
    assert report["instrumented_metrics"]["confidence_percent"] == 100.0
    assert report["production_ready"] is True
    assert report["status"] == "READY_FOR_HUMAN_DECISION"


def test_failed_smoke_blocks_production():
    runtime = {"endpoints": [{"name": "health", "ok": False, "http_code": 503, "latency_ms": 90}]}
    report = build_report([], successful_runs(), {"status": "READY", "metric_coverage_percent": 100}, {"snapshots": [{}, {}, {}, {}, {}]}, runtime)
    assert report["production_ready"] is False
    assert report["next_safe_increment"] == "restore_runtime_and_smoke_evidence"
    assert "runtime_smoke_failure" in report["human_blockers"]
