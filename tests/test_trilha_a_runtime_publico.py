from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "trilha_a_runtime_publico.py"
AAC = ROOT / "docs" / "architecture" / "trilha-a" / "architecture-as-code.json"
REPORT = ROOT / "audit" / "trilha-a" / "trilha-a-runtime-publico-report.json"


def test_trilha_a_governance_files_exist() -> None:
    required = [
        "docs/adr/ADR-036-trilha-a-runtime-publico.md",
        "docs/runbooks/trilha-a-runtime-publico.md",
        ".github/workflows/trilha-a-runtime-publico.yml",
        "docs/contracts/trilha-a-runtime-publico.schema.json",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel


def test_trilha_a_architecture_as_code_valid() -> None:
    payload = json.loads(AAC.read_text(encoding="utf-8"))
    assert payload["trail_id"] == "trilha-a"
    assert payload["mode"] == "report_only"
    assert "boot_resiliente" in payload["capabilities"]


def test_trilha_a_validator_generates_report() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode in (0, 1)
    assert REPORT.exists()
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["trail_id"] == "trilha-a"
    assert report["status"] in ("passed", "passed_with_warnings", "failed")
