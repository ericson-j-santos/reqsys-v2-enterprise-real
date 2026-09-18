from __future__ import annotations

import json
from pathlib import Path

from scripts.main_operational_validation_fast import run_fast_validation


def test_run_fast_validation_produces_summary(tmp_path: Path) -> None:
    output_dir = tmp_path / "fast"
    summary = run_fast_validation(
        repo="owner/repo",
        branch="main",
        sha="abc123",
        run_id="1",
        workflow_url="https://example.com/run/1",
        root=Path("."),
        output_dir=output_dir,
        skip_pytest=True,
    )
    assert summary["fast_path"] is True
    assert summary["elapsed_ms"] >= 0
    assert summary["guardrails_ok"] is True
    assert (output_dir / "main-operational-validation-fast.json").exists()
    assert Path("artifacts/operational-runtime-mesh-hub/operational-runtime-mesh-hub.json").exists()
    assert Path("artifacts/unified-operational-signal-consolidator/unified-operational-signal.json").exists()
    assert Path("artifacts/main-operational-health/evidence.json").exists()

    health = json.loads(Path("artifacts/main-operational-health/evidence.json").read_text(encoding="utf-8"))
    assert health["fast_path"] is True


def test_run_fast_validation_lite_is_faster_json_only(tmp_path: Path) -> None:
    mesh = Path("artifacts/operational-runtime-mesh-hub")
    alert = Path("artifacts/operational-alert-intelligence")
    for path in mesh.glob("*"):
        if path.suffix in {".html", ".md"}:
            path.unlink()
    for path in alert.glob("*"):
        if path.suffix in {".html", ".md"}:
            path.unlink()

    output_dir = tmp_path / "fast-lite"
    summary = run_fast_validation(
        repo="owner/repo",
        branch="main",
        sha="abc123",
        run_id="1",
        workflow_url="https://example.com/run/1",
        root=Path("."),
        output_dir=output_dir,
        lite=True,
    )
    assert summary["lite"] is True
    assert summary["elapsed_ms"] < 500
    assert (mesh / "operational-runtime-mesh-hub.json").exists()
    assert not (mesh / "operational-runtime-mesh-hub.html").exists()
    assert not (mesh / "operational-runtime-mesh-hub.md").exists()
    assert (alert / "operational-alert-intelligence.json").exists()
    assert not (alert / "operational-alert-intelligence.html").exists()
