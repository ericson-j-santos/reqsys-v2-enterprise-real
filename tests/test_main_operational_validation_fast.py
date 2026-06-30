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
    assert (output_dir / "operational-runtime-mesh-hub/operational-runtime-mesh-hub.json").exists()
    assert (output_dir / "unified-operational-signal-consolidator/unified-operational-signal.json").exists()
    assert (output_dir / "main-operational-health/evidence.json").exists()

    health = json.loads((output_dir / "main-operational-health/evidence.json").read_text(encoding="utf-8"))
    assert health["fast_path"] is True
