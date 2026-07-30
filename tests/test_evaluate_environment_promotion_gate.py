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


def tolerance(
    scope: str,
    *,
    decision: str = "allow",
    active: bool = True,
    tolerated=None,
    blocking=None,
    production_allowed: bool = False,
):
    return {
        "scope": scope,
        "decision": decision,
        "policy_active": active,
        "tolerated_controls": tolerated or [],
        "blocking_controls": blocking or [],
        "production_deployment_allowed": production_allowed,
        "automatic_blocking": decision == "block" or bool(blocking),
    }


def test_prod_approved_with_complete_green_evidence():
    result = evaluate(
        "prod",
        readiness(),
        {"status": "completed", "critical_pending": 0},
        tolerance("prod", production_allowed=True),
    )
    assert result["decision"] == "approved"
    assert result["should_fail_workflow"] is False


def test_prod_blocks_low_readiness():
    result = evaluate(
        "prod",
        readiness(score=80),
        {"status": "completed", "critical_pending": 0},
        tolerance("prod", production_allowed=True),
    )
    assert result["decision"] == "blocked"
    assert result["should_fail_workflow"] is True
    assert "readiness_below_threshold" in result["reasons"]


def test_prod_never_false_green_with_missing_source():
    result = evaluate(
        "prod",
        readiness(sources={"runtime_validation": True, "ci_lead_time": False}),
        {"status": "completed", "critical_pending": 0},
        tolerance("prod", production_allowed=True),
    )
    assert result["decision"] == "insufficient_evidence"
    assert result["should_fail_workflow"] is True


def test_stg_is_warning_only_during_stabilization():
    result = evaluate(
        "stg",
        readiness(score=75, coverage=85, ci=85),
        {},
        tolerance("stg"),
    )
    assert result["decision"] == "approved_with_warning"
    assert result["blocking"] is False
    assert result["should_fail_workflow"] is False


def test_critical_pending_blocks_prod():
    result = evaluate(
        "prod",
        readiness(),
        {"status": "completed", "critical_pending": 1},
        tolerance("prod", production_allowed=True),
    )
    assert result["decision"] == "blocked"
    assert result["should_fail_workflow"] is True


def test_stg_allows_active_partial_controls_with_explicit_warning():
    result = evaluate(
        "stg",
        readiness(),
        {"status": "completed", "critical_pending": 0},
        tolerance("stg", tolerated=["BACEN-01", "BACEN-08"]),
    )
    assert result["decision"] == "approved_with_warning"
    assert result["should_fail_workflow"] is False
    assert "bacen_partial_controls_temporarily_tolerated" in result["warnings"]
    assert result["evidence"]["bacen_tolerated_controls"] == ["BACEN-01", "BACEN-08"]


def test_stg_blocks_expired_or_rejected_tolerance():
    result = evaluate(
        "stg",
        readiness(),
        {"status": "completed", "critical_pending": 0},
        tolerance("stg", decision="block", active=False, blocking=["BACEN-01"]),
    )
    assert result["decision"] == "blocked"
    assert result["blocking"] is True
    assert result["should_fail_workflow"] is True
    assert "bacen_nonprod_tolerance_blocked" in result["reasons"]


def test_prod_blocks_partial_controls_even_when_nonprod_tolerance_exists():
    result = evaluate(
        "prod",
        readiness(),
        {"status": "completed", "critical_pending": 0},
        tolerance(
            "prod",
            decision="block",
            tolerated=["BACEN-01"],
            blocking=["BACEN-01"],
            production_allowed=False,
        ),
    )
    assert result["decision"] == "blocked"
    assert result["should_fail_workflow"] is True
    assert "bacen_partial_controls_block_production" in result["reasons"]


def test_prod_blocks_when_bacen_evidence_is_missing():
    result = evaluate(
        "prod",
        readiness(),
        {"status": "completed", "critical_pending": 0},
        {},
    )
    assert result["decision"] == "blocked"
    assert result["should_fail_workflow"] is True
    assert "bacen_production_evidence_missing" in result["reasons"]
