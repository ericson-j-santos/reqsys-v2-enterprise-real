from scripts.update_instrumented_executive_history import update_history


def snapshot(at: str, technical: float, production: float, operational: float) -> dict:
    return {
        "contract": "reqsys-instrumented-executive-readiness",
        "generated_at": at,
        "metric_coverage_percent": 100,
        "operational_readiness_percent": operational,
        "indicators": {
            "technical_progress_percent": technical,
            "production_percent": production,
        },
    }


def test_first_snapshot_has_no_projection_before_target() -> None:
    result = update_history({}, snapshot("2026-07-20T00:00:00+00:00", 80, 70, 75))
    assert result["snapshot_count"] == 1
    assert result["eta"]["mvp"]["status"] == "insufficient_history"
    assert result["eta"]["mvp"]["eta_days"] is None


def test_positive_velocity_projects_eta() -> None:
    first = snapshot("2026-07-20T00:00:00+00:00", 80, 70, 75)
    history = update_history({}, first)
    result = update_history(history, snapshot("2026-07-22T00:00:00+00:00", 84, 80, 85))
    assert result["snapshot_count"] == 2
    assert result["eta"]["mvp"]["status"] == "projected"
    assert result["eta"]["mvp"]["velocity_percent_per_day"] == 2.0
    assert result["eta"]["mvp"]["eta_days"] == 3.0


def test_achieved_milestone_has_zero_eta_and_deduplicates() -> None:
    point = snapshot("2026-07-20T00:00:00+00:00", 95, 96, 97)
    history = update_history({}, point)
    result = update_history(history, point)
    assert result["snapshot_count"] == 1
    assert result["eta"]["mvp"]["status"] == "achieved"
    assert result["eta"]["production"]["eta_days"] == 0.0


def test_non_positive_velocity_does_not_invent_eta() -> None:
    history = update_history({}, snapshot("2026-07-20T00:00:00+00:00", 80, 80, 80))
    result = update_history(history, snapshot("2026-07-22T00:00:00+00:00", 79, 79, 79))
    assert result["eta"]["mvp"]["status"] == "no_positive_velocity"
    assert result["eta"]["mvp"]["eta_days"] is None
