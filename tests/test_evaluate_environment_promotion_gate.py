from scripts.evaluate_environment_promotion_gate import evaluate


def readiness(score=96, coverage=100, ci=98, sources=None):
    return {
        "operational_readiness_percent": score,
        "metric_coverage_percent": coverage,
        "indicators": {"ci_stability_percent": ci},
        "sources": sources
        or {
            "consumer_readiness": True,
            "runtime_validation": True,
            "merge_intelligence": True,
            "ci_lead_time": True,
        },
        "correlation_id": "test-correlation",
    }


def test_prod_approved_with_complete_green_evidence():
    result = evaluate("prod", readiness(), {"status": "completed", "critical_pending": 0})
    assert result["decision"] == "approved"
    assert result["should_fail_workflow"] is False


def test_prod_blocks_low_readiness():
    result = evaluate("prod", readiness(score=80), {"status": "completed", "critical_pending": 0})
    assert result["decision"] == "blocked"
    assert result["should_fail_workflow"] is True
    assert "readiness_below_threshold" in result["reasons"]


def test_prod_never_false_green_with_missing_source():
    result = evaluate(
        "prod",
        readiness(sources={"runtime_validation": True, "ci_lead_time": False}),
        {"status": "completed", "critical_pending": 0},
    )
    assert result["decision"] == "insufficient_evidence"
    assert result["should_fail_workflow"] is True


def test_stg_is_warning_only_during_stabilization():
    result = evaluate("stg", readiness(score=75, coverage=85, ci=85), {})
    assert result["decision"] == "approved_with_warning"
    assert result["blocking"] is False
    assert result["should_fail_workflow"] is False


def test_critical_pending_blocks_prod():
    result = evaluate("prod", readiness(), {"status": "completed", "critical_pending": 1})
    assert result["decision"] == "blocked"
    assert result["should_fail_workflow"] is True
