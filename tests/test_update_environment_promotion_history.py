from scripts.update_environment_promotion_history import build_history


def decision(status="approved", run_id=1, environment="stg"):
    return {
        "environment": environment,
        "decision": status,
        "generated_at": f"2026-07-21T01:{run_id:02d}:00+00:00",
        "run_id": run_id,
        "sha": f"sha-{run_id}",
        "readiness_percent": 96,
        "metric_coverage_percent": 100,
    }


def append(history, item):
    return build_history(history, item)


def test_requires_five_stg_executions():
    history = {}
    for index in range(1, 5):
        history = append(history, decision(run_id=index))
    maturity = history["stg_enforcement_maturity"]
    assert maturity["criteria_met"] is False
    assert maturity["observed_window"] == 4


def test_ready_with_four_approved_and_one_warning():
    history = {}
    for index, status in enumerate(["approved", "approved", "approved_with_warning", "approved", "approved"], 1):
        history = append(history, decision(status=status, run_id=index))
    maturity = history["stg_enforcement_maturity"]
    assert maturity["criteria_met"] is True
    assert maturity["status"] == "ready_for_human_approval"
    assert maturity["automatic_change_allowed"] is False


def test_blocked_decision_prevents_maturity():
    history = {}
    for index, status in enumerate(["approved", "approved", "blocked", "approved", "approved"], 1):
        history = append(history, decision(status=status, run_id=index))
    assert history["stg_enforcement_maturity"]["criteria_met"] is False


def test_duplicate_execution_is_idempotent():
    history = append({}, decision(run_id=1))
    history = append(history, decision(run_id=1))
    assert history["point_count"] == 1


def test_dev_execution_does_not_count_for_stg_window():
    history = append({}, decision(run_id=1, environment="dev"))
    assert history["stg_enforcement_maturity"]["observed_window"] == 0
