from __future__ import annotations

import json
from pathlib import Path

from scripts.build_runtime_production_smoke_governed import build_snapshot, classify, main


def _validation(success: float = 100.0, failed: int = 0) -> dict:
    return {
        "environment": "prod",
        "base_url": "https://reqsys-api.fly.dev",
        "total": 4,
        "ok": 4 - failed,
        "failed": failed,
        "success_percentual": success,
        "readiness": _readiness(),
    }


def _readiness(percent: float = 100.0, blocking: list[str] | None = None) -> dict:
    return {
        "operational_status": "healthy",
        "readiness_percent": percent,
        "blocking_issues": blocking or [],
        "api_ready": True,
        "runtime_ready": True,
        "dashboard_ready": True,
    }


def test_classify_green_when_smoke_and_readiness_are_complete() -> None:
    state, blockers = classify(_validation(), _readiness())

    assert state == "green"
    assert blockers == []


def test_classify_yellow_for_partial_but_reachable_runtime() -> None:
    state, blockers = classify(_validation(success=75.0, failed=1), _readiness(percent=80.0))

    assert state == "yellow"
    assert "required_endpoint_failed" in blockers


def test_classify_red_when_validation_missing() -> None:
    state, blockers = classify(None, None)

    assert state == "red"
    assert blockers == ["public_runtime_validation_missing"]


def test_build_snapshot_preserves_read_only_guardrails() -> None:
    snapshot = build_snapshot(
        _validation(),
        _readiness(),
        repository="ericson-j-santos/reqsys-v2-enterprise-real",
        branch="main",
        sha="abc123",
        run_id="12345",
    )

    assert snapshot["contract"] == "runtime-production-smoke-governed"
    assert snapshot["state"] == "green"
    assert snapshot["production_ready"] is True
    assert snapshot["guardrails"]["read_only"] is True
    assert snapshot["guardrails"]["deploy"] is False
    assert snapshot["guardrails"]["merge"] is False


def test_main_writes_json_and_summary(tmp_path: Path, monkeypatch) -> None:
    runtime_dir = tmp_path / "artifacts/runtime"
    runtime_dir.mkdir(parents=True)
    validation_path = runtime_dir / "public-runtime-validation.json"
    readiness_path = runtime_dir / "ops-readiness-report.json"
    output_dir = tmp_path / "out"
    validation_path.write_text(json.dumps(_validation()), encoding="utf-8")
    readiness_path.write_text(json.dumps(_readiness()), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "build_runtime_production_smoke_governed.py",
            "--validation",
            str(validation_path),
            "--readiness",
            str(readiness_path),
            "--output-dir",
            str(output_dir),
            "--repository",
            "repo/name",
            "--branch",
            "main",
            "--sha",
            "abc123",
            "--run-id",
            "12345",
            "--enforce",
        ],
    )

    assert main() == 0
    assert (output_dir / "runtime-production-smoke-governed.json").exists()
    assert (output_dir / "summary.md").exists()
