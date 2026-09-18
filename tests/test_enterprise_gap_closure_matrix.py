from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/padrao-ouro/enterprise-gap-closure-matrix.json"


def test_enterprise_gap_matrix_is_valid_json_and_prioritized() -> None:
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    gaps = payload["gaps"]

    assert payload["schema_version"] == "1.0.0"
    assert len(gaps) >= 6
    assert {"P0", "P1", "P2"}.issubset({gap["priority"] for gap in gaps})
    assert all(gap["target_maturity_percent"] > gap["current_maturity_percent"] for gap in gaps)
    assert any(gap["pillar"] == "ux_enterprise" for gap in gaps)
    assert any(gap["pillar"] == "seguranca_governanca" for gap in gaps)


def test_enterprise_gap_matrix_cli_reports_pareto_summary() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/enterprise_gap_closure_matrix.py", "--matrix", str(MATRIX)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    result = json.loads(completed.stdout)

    assert result["valid"] is True
    assert result["summary"]["gap_count"] >= 6
    assert "OPS-GAP-AGENT-RUNTIME-001" in result["summary"]["top_pareto"]
