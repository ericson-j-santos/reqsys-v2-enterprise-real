from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "trilha_b_observabilidade_enterprise.py"
REPORT = ROOT / "audit" / "trilha-b" / "trilha-b-observabilidade-enterprise-report.json"


def test_trilha_b_governance_files_exist() -> None:
    required = [
        "docs/adr/ADR-037-trilha-b-observabilidade-enterprise.md",
        "docs/runbooks/trilha-b-observabilidade-enterprise.md",
        ".github/workflows/trilha-b-observabilidade-enterprise.yml",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel


def test_trilha_b_validator_passes() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["trail_id"] == "trilha-b"
    assert report["status"] == "passed"
