"""Tests for Operational Observability Hub increment."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture()
def sample_env_validation(tmp_path: Path) -> Path:
    payload = {
        "environments": [
            {
                "name": "desenvolvimento",
                "frontend": "https://reqsys-app-dev.fly.dev",
                "api": "https://reqsys-api-dev.fly.dev/docs",
                "status": "ready",
                "readiness_percent": 100,
                "operational_risk": "low",
            },
            {
                "name": "homologacao",
                "frontend": "https://reqsys-web-stg.fly.dev",
                "api": "https://reqsys-api-stg.fly.dev/docs",
                "status": "degraded",
                "readiness_percent": 50,
                "operational_risk": "medium",
            },
            {
                "name": "producao",
                "frontend": "https://reqsys-app.fly.dev",
                "api": "https://reqsys-api.fly.dev/docs",
                "status": "ready",
                "readiness_percent": 100,
                "operational_risk": "low",
            },
        ],
        "summary": {"average_readiness_percent": 83.33, "overall_status": "degraded"},
    }
    path = tmp_path / "environments-validation.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture()
def sample_history(tmp_path: Path) -> Path:
    history = [
        {
            "snapshot_at_utc": "2026-06-20T10:00:00+00:00",
            "hub_score": 70,
            "hub_status": "ATENCAO",
            "metrics": {"overall_failure_rate_percent": 10, "mttr_minutes": 45},
        },
        {
            "snapshot_at_utc": "2026-06-27T10:00:00+00:00",
            "hub_score": 85,
            "hub_status": "SAUDAVEL",
            "metrics": {"overall_failure_rate_percent": 3, "mttr_minutes": 30},
        },
    ]
    out_dir = tmp_path / "operational-history"
    out_dir.mkdir()
    path = out_dir / "operational-history.json"
    path.write_text(json.dumps(history), encoding="utf-8")
    trend_path = out_dir / "operational-history-trend.json"
    trend_path.write_text(
        json.dumps({"direction": "melhorando", "points": 2, "last_score": 85}),
        encoding="utf-8",
    )
    return path


def test_multi_environment_evidence_consolidation(sample_env_validation: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "multi-env"
    result = _run(
        "scripts/operational_multi_environment_evidence.py",
        "--environments-validation",
        str(sample_env_validation),
        "--fly-matrix",
        str(ROOT / "infra/fly-environments.json"),
        "--out-dir",
        str(out_dir),
    )
    assert result.returncode == 0
    report = json.loads((out_dir / "multi-environment-evidence.json").read_text(encoding="utf-8"))
    assert report["mode"] == "report_only"
    canonical = {item["canonical"] for item in report["environments"]}
    assert "dev" in canonical
    assert "hml" in canonical
    assert "prod" in canonical


def test_environment_drift_detects_promotion_inversion(sample_env_validation: Path, tmp_path: Path) -> None:
    multi_dir = tmp_path / "multi-env"
    drift_dir = tmp_path / "drift"
    _run(
        "scripts/operational_multi_environment_evidence.py",
        "--environments-validation",
        str(sample_env_validation),
        "--fly-matrix",
        str(ROOT / "infra/fly-environments.json"),
        "--out-dir",
        str(multi_dir),
    )
    result = _run(
        "scripts/environment_drift_analyzer.py",
        "--multi-env",
        str(multi_dir / "multi-environment-evidence.json"),
        "--out-dir",
        str(drift_dir),
    )
    assert result.returncode == 0
    report = json.loads((drift_dir / "environment-drift.json").read_text(encoding="utf-8"))
    assert report["drift_level"] in {"ALTO", "MEDIO", "BAIXO", "NENHUM"}
    finding_types = {item["type"] for item in report.get("findings", [])}
    assert "promotion_inversion" in finding_types or report["drift_level"] != "NENHUM"


def test_slo_evidence_from_history(sample_env_validation: Path, sample_history: Path, tmp_path: Path) -> None:
    multi_dir = tmp_path / "multi-env"
    slo_dir = tmp_path / "slo"
    _run(
        "scripts/operational_multi_environment_evidence.py",
        "--environments-validation",
        str(sample_env_validation),
        "--fly-matrix",
        str(ROOT / "infra/fly-environments.json"),
        "--out-dir",
        str(multi_dir),
    )
    result = _run(
        "scripts/generate_operational_slo_evidence.py",
        "--history",
        str(sample_history),
        "--multi-env",
        str(multi_dir / "multi-environment-evidence.json"),
        "--out-dir",
        str(slo_dir),
    )
    assert result.returncode == 0
    report = json.loads((slo_dir / "operational-slo-evidence.json").read_text(encoding="utf-8"))
    assert report["summary"]["slo_count"] == 3
    ci_slo = next(item for item in report["slos"] if item["slo_id"] == "ci_success_rate")
    assert ci_slo["actual_percent"] == 97.0


def test_longitudinal_analytics(sample_history: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "longitudinal"
    history_dir = sample_history.parent
    result = _run(
        "scripts/operational_longitudinal_analytics.py",
        "--history",
        str(sample_history),
        "--trend",
        str(history_dir / "operational-history-trend.json"),
        "--out-dir",
        str(out_dir),
    )
    assert result.returncode == 0
    report = json.loads((out_dir / "longitudinal-analytics.json").read_text(encoding="utf-8"))
    assert report["history_points_total"] == 2
    assert report["windows"]["7d"]["points"] >= 1


def test_correlation_timeline_hydrated(tmp_path: Path) -> None:
    hub_dir = tmp_path / "hub"
    hub_dir.mkdir()
    hub = {
        "correlation_id": "test-correlation",
        "operational_risk": "low",
        "correlation_chain": [
            {"sequence": 1, "event": "ci_workflow_run", "correlation_level": "ci"},
            {"sequence": 2, "event": "environment_probe", "correlation_level": "runtime"},
        ],
    }
    (hub_dir / "operational-observability-hub.json").write_text(json.dumps(hub), encoding="utf-8")
    out_dir = tmp_path / "reports" / "github-runtime-analytics"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/product_intelligence/generate_runtime_operational_correlation_timeline.py"),
            "--hub",
            str(hub_dir / "operational-observability-hub.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**dict(**{"PYTHONPATH": str(ROOT)}), **dict(__import__("os").environ)},
    )
    assert result.returncode == 0
    timeline_path = ROOT / "reports/github-runtime-analytics/runtime-operational-correlation-timeline.json"
    assert timeline_path.exists()
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    assert timeline["runtime_state"] == "TIMELINE_HYDRATED"
    assert timeline["timeline_event_count"] >= 3
