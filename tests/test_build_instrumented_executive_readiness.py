from scripts.build_instrumented_executive_readiness import build_contract


def fixtures():
    readiness = {"readiness_percent": 100}
    runtime = {
        "validation_score": 92,
        "confidence_percent": 91,
        "operational_risk_percent": 9,
        "production_ready": False,
        "domains": {"public_readiness": {"score": 90}},
        "gold_standard_operational_risk": {"overall_score": 88, "source_coverage_percent": 80},
    }
    merge = {
        "merge_intelligence": {"mergeability_score": 88, "queue_pressure": 12},
        "trend": {"parallel_lanes_active": ["a", "b", "c", "d"]},
    }
    ci = {"summary": {"success_rate_percent": 96}}
    return readiness, runtime, merge, ci


def test_builds_only_instrumented_metrics():
    contract = build_contract(*fixtures())
    indicators = contract["indicators"]
    assert contract["metric_coverage_percent"] == 100
    assert indicators["ci_stability_percent"] == 96
    assert indicators["active_parallel_lanes"] == 4
    assert indicators["throughput_parallel_class"] == "high"
    assert contract["mode"] == "report_only"
    assert contract["automatic_promotion_allowed"] is False


def test_missing_ci_is_explicit_not_invented():
    readiness, runtime, merge, _ = fixtures()
    contract = build_contract(readiness, runtime, merge, {})
    assert contract["indicators"]["ci_stability_percent"] is None
    assert contract["metric_coverage_percent"] < 100
    assert contract["milestones"]["eta_calendar"] is None
    assert contract["next_safe_increment"] == "collect_ci_lead_time_artifact"


def test_ready_requires_production_evidence():
    readiness, runtime, merge, ci = fixtures()
    runtime["validation_score"] = 100
    runtime["production_ready"] = True
    runtime["gold_standard_operational_risk"]["overall_score"] = 100
    contract = build_contract(readiness, runtime, merge, ci)
    assert contract["status"] == "READY"
    assert contract["milestones"]["production"] == "ready"
