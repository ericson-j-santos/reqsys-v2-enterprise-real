from __future__ import annotations

import json
from pathlib import Path

from scripts.build_continuous_trilha_d_monitoring_history import (
    build_metrics,
    build_payload,
    ingest_monitoring_snapshot,
    merge_history,
    snapshot_from_monitoring,
    write_payload,
)


def _monitoring(*, state: str = "green", alerts_active: int = 0) -> dict:
    return {
        "state": state,
        "monitoring_enabled": True,
        "regression_alert": False,
        "alerts_active": alerts_active,
        "summary": {"recommendation": "monitoramento_estavel"},
        "signals": {"predictive_risk": "low", "trend": "improving"},
    }


def test_snapshot_from_monitoring_captura_estado() -> None:
    snapshot = snapshot_from_monitoring(_monitoring(alerts_active=1), run_id="12345")
    assert snapshot["state"] == "green"
    assert snapshot["alerts_active"] == 1
    assert "12345" in snapshot["workflow_run_url"]


def test_build_metrics_calcula_taxas() -> None:
    history = [
        {"state": "green", "alerts_active": 0, "regression_alert": False},
        {"state": "yellow", "alerts_active": 1, "regression_alert": False},
    ]
    metrics = build_metrics(history)
    assert metrics["samples"] == 2
    assert metrics["green_rate"] == 0.5
    assert metrics["alerting_samples"] == 1


def test_ingest_monitoring_snapshot_appenda_historico(tmp_path: Path) -> None:
    monitoring = tmp_path / "monitoring.json"
    output = tmp_path / "history.json"
    monitoring.write_text(json.dumps(_monitoring()), encoding="utf-8")

    payload = ingest_monitoring_snapshot(str(monitoring), str(output), run_id="run-1")
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert payload["summary"]["continuous_trilha_d_monitoring_history_enabled"] is True
    assert loaded["history"][-1]["run_id"] == "run-1"
    assert payload["summary"]["monitoring_stabilized"] is True


def test_merge_history_deduplica_por_run_id() -> None:
    existing = [{"run_id": "run-1", "state": "yellow"}]
    snapshot = snapshot_from_monitoring(_monitoring(), run_id="run-1")
    history = merge_history(existing, snapshot)
    assert len(history) == 1
    assert history[0]["state"] == "green"


def test_write_payload_creates_valid_json(tmp_path: Path) -> None:
    output = tmp_path / "history.json"
    payload = write_payload(str(output), history=[snapshot_from_monitoring(_monitoring())])
    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["repo"] == payload["repo"]
    assert loaded["summary"]["samples"] == 1
