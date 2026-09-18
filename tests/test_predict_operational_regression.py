from __future__ import annotations

import json
from pathlib import Path

from scripts.predict_operational_regression import predict_operational_regression, should_fail


def _history_index(*, trend: str = "stable", regressing: list[str] | None = None) -> dict:
    dimension_summary = {
        dimension: {
            "current_status": "passed",
            "current_score": 95.0,
            "previous_score": 94.0,
            "delta_from_baseline": 1.0,
            "trend": "regressing" if dimension in (regressing or []) else "stable",
            "samples": 3,
        }
        for dimension in ("tests", "coverage", "mutation", "contract", "schema", "ci-watch")
    }
    return {
        "current_score": 95.0,
        "baseline_score": 90.0,
        "delta_from_baseline": 5.0,
        "trend": trend,
        "dimension_summary": dimension_summary,
        "history": [
            {
                "timestamp": "2026-06-27T00:00:00Z",
                "run_id": "1",
                "state": "green",
                "average_score": 90.0,
                "dimensions": {},
            },
            {
                "timestamp": "2026-06-28T00:00:00Z",
                "run_id": "2",
                "state": "green",
                "average_score": 95.0,
                "dimensions": {},
            },
        ],
    }


def test_predict_allows_stable_history_without_paths() -> None:
    result = predict_operational_regression(_history_index())

    assert result["risk"] == "low"
    assert result["regression_predicted"] is False
    assert result["parallel_safe"] is True
    assert result["recommendation"] == "merge_paralelo_seguro"
    assert result["links"]["dashboard_data"].endswith("predictive-regression-gate.json")


def test_predict_marks_overall_regressing_trend() -> None:
    result = predict_operational_regression(_history_index(trend="regressing"))

    assert result["risk"] == "medium"
    assert result["regression_predicted"] is True
    assert "overall_trend_regressing" in result["blocking_reasons"]


def test_predict_marks_critical_dimension_regression_as_high() -> None:
    result = predict_operational_regression(_history_index(regressing=["coverage"]))

    assert result["risk"] == "high"
    assert "coverage" in result["signals"]["critical_regressing_dimensions"]


def test_predict_blocks_when_paths_touch_regressing_dimension_in_blocking_mode() -> None:
    result = predict_operational_regression(
        _history_index(regressing=["coverage"]),
        changed_paths=["backend/tests/test_auth_critical_paths.py"],
        mode="blocking",
    )

    assert result["risk"] == "blocked"
    assert result["parallel_safe"] is False
    assert should_fail(result) is True


def test_predict_projected_drop_from_current_report() -> None:
    history = _history_index()
    report = {"average_score": 90.0, "state": "passed"}

    result = predict_operational_regression(history, current_report=report)

    assert result["regression_predicted"] is True
    assert result["signals"]["projected_drop"] is True
    assert result["risk"] == "high"


def test_predict_insufficient_history_stays_low_risk() -> None:
    history = _history_index()
    history["history"] = history["history"][:1]

    result = predict_operational_regression(history, min_samples=2)

    assert result["risk"] == "low"
    assert result["signals"]["insufficient_history"] is True


def test_main_writes_artifact(tmp_path: Path, monkeypatch) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps(_history_index()), encoding="utf-8")
    output = tmp_path / "gate.json"

    from scripts import predict_operational_regression as module

    exit_code = module.main(
        [
            "--history-json",
            str(history_path),
            "--output",
            str(output),
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0.0"
