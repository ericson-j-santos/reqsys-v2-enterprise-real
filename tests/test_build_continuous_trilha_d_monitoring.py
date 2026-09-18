from __future__ import annotations

import json
from pathlib import Path

from scripts.build_continuous_trilha_d_monitoring import (
    build_alerts,
    build_payload,
    resolve_monitoring_state,
    write_payload,
)


def _history(*, artifact_ingestion: bool = True, trend: str = "improving", failed_samples: int = 0) -> dict:
    return {
        "current_score": 97.0,
        "trend": trend,
        "summary": {
            "artifact_ingestion_enabled": artifact_ingestion,
            "failed_samples": failed_samples,
            "next_increment": "continuous_trilha_d_monitoring",
        },
    }


def _predictive(*, regression_predicted: bool = False, blocking_reasons: list[str] | None = None) -> dict:
    return {
        "risk": "low",
        "regression_predicted": regression_predicted,
        "blocking_reasons": blocking_reasons or [],
        "signals": {
            "regressing_dimensions": [],
            "projected_drop": False,
            "recent_failed_samples": 0,
        },
    }


def test_build_alerts_stable_when_signals_healthy() -> None:
    alerts = build_alerts(_history(), _predictive())
    assert alerts == []
    assert resolve_monitoring_state(alerts) == "green"


def test_build_alerts_flags_regression_predicted() -> None:
    alerts = build_alerts(_history(), _predictive(regression_predicted=True))
    assert any(alert["code"] == "regression_predicted" for alert in alerts)
    assert resolve_monitoring_state(alerts) == "red"


def test_build_alerts_flags_failed_samples_and_disabled_ingestion() -> None:
    predictive = _predictive()
    predictive["signals"]["recent_failed_samples"] = 2
    alerts = build_alerts(_history(artifact_ingestion=False, failed_samples=2), predictive)
    codes = {alert["code"] for alert in alerts}
    assert "artifact_ingestion_disabled" in codes
    assert "recent_failed_samples" in codes
    assert "failed_samples_in_history" not in codes
    assert resolve_monitoring_state(alerts) == "yellow"


def test_build_alerts_ignores_cumulative_failed_samples_when_recent_is_zero() -> None:
    predictive = _predictive()
    alerts = build_alerts(_history(failed_samples=3), predictive)
    assert alerts == []
    assert resolve_monitoring_state(alerts) == "green"


def test_build_payload_exposes_runtime_contract() -> None:
    payload = build_payload()
    assert payload["schema_version"] == "1.0.0"
    assert "monitoring_enabled" in payload
    assert payload["runtime_dashboard_contract"]["refresh_strategy"]
    assert payload["links"]["dashboard_data"]


def test_build_payload_usa_next_increment_resolvido(tmp_path: Path, monkeypatch) -> None:
    history = tmp_path / "history.json"
    predictive = tmp_path / "predictive.json"
    history.write_text(json.dumps(_history(artifact_ingestion=True)), encoding="utf-8")
    predictive.write_text(json.dumps(_predictive()), encoding="utf-8")
    monkeypatch.setattr(
        "scripts.build_trilha_d_history.resolve_next_increment",
        lambda artifact_ingestion, repo_root=None: (
            "merge_readiness_history" if artifact_ingestion else "artifact_ingestion_refresh"
        ),
    )

    payload = build_payload(history_path=history, predictive_path=predictive)

    assert payload["summary"]["next_increment"] == "merge_readiness_history"


def test_write_payload_creates_valid_json(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    predictive = tmp_path / "predictive.json"
    output = tmp_path / "monitoring.json"
    history.write_text(json.dumps(_history()), encoding="utf-8")
    predictive.write_text(json.dumps(_predictive()), encoding="utf-8")

    payload = write_payload(str(output), history_path=history, predictive_path=predictive)
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert loaded["repo"] == payload["repo"]
    assert loaded["alerts_active"] == 0
