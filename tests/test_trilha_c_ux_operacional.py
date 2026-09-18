from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "trilha_c_ux_operacional.py"
REPORT = ROOT / "audit" / "trilha-c" / "trilha-c-ux-operacional-report.json"


def test_trilha_c_governance_files_exist() -> None:
    required = [
        "docs/adr/ADR-038-trilha-c-ux-operacional.md",
        "docs/runbooks/trilha-c-ux-operacional.md",
        ".github/workflows/trilha-c-ux-operacional.yml",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel


def test_trilha_c_validator_passes() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["trail_id"] == "trilha-c"
    assert report["status"] == "passed"
