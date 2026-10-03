from pathlib import Path

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
        {
            "name": name,
            "status": "completed",
            "conclusion": "success",
            "created_at": "2026-07-21T10:00:00Z",
            "updated_at": "2026-07-21T10:05:00Z",
        }
        for name in NAMES
    ]


def healthy_runtime(**overrides):
    payload = {
        "observed_at": "2026-07-21T10:20:00Z",
        "build_sha": "unknown",
        "environment": "dev",
        "endpoints": [
            {"name": "health", "ok": True, "http_code": 200, "latency_ms": 90},
            {"name": "readiness", "ok": True, "http_code": 200, "latency_ms": 100},
            {"name": "liveness", "ok": True, "http_code": 200, "latency_ms": 110},
        ],
    }
    payload.update(overrides)
    return payload


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
    assert report["runtime"]["average_latency_ms"] == 100.0
    assert report["integration"]["median_merge_lead_time_hours"] == 36.0
    assert report["delivery_velocity"]["merge_lead_time"]["median_minutes"] == 2160.0
    assert report["instrumented_metrics"]["trend_delta_percent"] == 10.0
    assert report["instrumented_metrics"]["confidence_percent"] == 100.0
    assert report["production_ready"] is True
    assert report["status"] == "READY_FOR_HUMAN_DECISION"


def test_measures_sha_linked_merge_ci_and_runtime_intervals():
    merge_sha = "a" * 40
    merged_prs = [
        {
            "number": 101,
            "created_at": "2026-07-21T09:00:00Z",
            "merged_at": "2026-07-21T10:00:00Z",
            "merge_commit_sha": merge_sha,
        }
    ]
    runs = successful_runs()
    runs[0].update({
        "head_sha": merge_sha,
        "created_at": "2026-07-21T10:00:10Z",
        "updated_at": "2026-07-21T10:05:00Z",
    })
    runtime = healthy_runtime(build_sha=merge_sha, observed_at="2026-07-21T10:20:00Z")

    report = build_report(
        [], runs, {"status": "READY", "metric_coverage_percent": 100},
        {"snapshots": [{}, {}, {}, {}, {}]}, runtime, merged_prs,
        availability_target_minutes=30,
    )

    delivery = report["delivery_velocity"]
    assert delivery["merge_to_ci_green"]["median_minutes"] == 5.0
    linked = delivery["sha_linked_runtime"]
    assert linked["matched_pr_number"] == 101
    assert linked["merge_to_runtime_observed_minutes"] == 20.0
    assert linked["created_to_runtime_observed_minutes"] == 80.0
    assert linked["target_met"] is True
    assert delivery["measurement_gaps"] == []
    assert delivery["wait_partition"]["external_blocked_minutes"] is None


def test_does_not_infer_runtime_availability_without_exact_sha_match():
    merge_sha = "a" * 40
    merged_prs = [
        {
            "number": 102,
            "created_at": "2026-07-21T09:00:00Z",
            "merged_at": "2026-07-21T10:00:00Z",
            "merge_commit_sha": merge_sha,
        }
    ]
    runtime = healthy_runtime(build_sha="b" * 40, observed_at="2026-07-21T10:10:00Z")
    report = build_report(
        [], successful_runs(), {"status": "READY", "metric_coverage_percent": 100},
        {"snapshots": [{}, {}, {}, {}, {}]}, runtime, merged_prs,
    )
    linked = report["delivery_velocity"]["sha_linked_runtime"]
    assert linked["merge_to_runtime_observed_minutes"] is None
    assert linked["target_met"] is None
    assert "runtime_build_sha_not_mapped_to_recent_merge" in report["delivery_velocity"]["measurement_gaps"]


def test_failed_smoke_blocks_production():
    runtime = {
        "observed_at": "2026-07-21T10:20:00Z",
        "build_sha": "unknown",
        "endpoints": [{"name": "health", "ok": False, "http_code": 503, "latency_ms": 90}],
    }
    report = build_report([], successful_runs(), {"status": "READY", "metric_coverage_percent": 100}, {"snapshots": [{}, {}, {}, {}, {}]}, runtime)
    assert report["production_ready"] is False
    assert report["next_safe_increment"] == "restore_runtime_and_smoke_evidence"
    assert "runtime_smoke_failure" in report["human_blockers"]


def test_workflow_uses_bounded_github_collection_contract():
    workflow = Path(".github/workflows/reqsys-next-increment-auto-evaluation.yml").read_text(encoding="utf-8")
    assert "--paginate" not in workflow
    assert "API_TIMEOUT_SECONDS: '30'" in workflow
    assert "MERGED_PR_MAX_PAGES: '2'" in workflow
    assert "RUN_MAX_PAGES: '3'" in workflow
    assert "COMMENT_MAX_PAGES: '3'" in workflow

    bounded_endpoints = [
        '"repos/${{ github.repository }}/pulls?state=open&per_page=100&page=1"',
        '"repos/${{ github.repository }}/pulls?state=closed&sort=updated&direction=desc&per_page=100&page=${page}"',
        '"repos/${{ github.repository }}/actions/runs?per_page=100&page=${page}"',
        '"repos/${{ github.repository }}/issues/${LEDGER_ISSUE}/comments?per_page=100&page=${page}"',
    ]
    for endpoint in bounded_endpoints:
        position = workflow.index(endpoint)
        prefix = workflow[max(0, position - 220):position]
        assert 'timeout "${API_TIMEOUT_SECONDS}s" gh api' in prefix

    assert "timeout-minutes: 10" in workflow
    assert "merge_commit_sha" in workflow
    assert "/api/runtime/build-info" in workflow
    assert "workflow_run:" in workflow
    assert "ReqSys Fly Runtime P0" in workflow
