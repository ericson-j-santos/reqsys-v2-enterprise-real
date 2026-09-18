from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "trilhas_padrao_ouro.py"
REGISTRY = ROOT / "docs" / "architecture" / "trilhas" / "trilhas-registry.json"
REPORT = ROOT / "audit" / "trilhas" / "trilhas-padrao-ouro-report.json"
SCHEMA = ROOT / "docs/contracts/trilhas-padrao-ouro.schema.json"


def test_registry_lists_five_trails() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert len(registry["trails"]) == 5
    ids = {t["id"] for t in registry["trails"]}
    assert ids == {"trilha-a", "trilha-b", "trilha-c", "trilha-d", "trilha-e"}


def test_consolidator_generates_report_with_required_fields() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert REPORT.exists(), proc.stderr
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for field in schema["required"]:
        assert field in report, field
    assert report["summary"]["trails_total"] == 5
    assert report["status"] == "passed"
    assert report["summary"]["gold_standard_percent"] == 100.0


def test_all_trails_have_governance_criteria() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for trail in registry["trails"]:
        for key in ("adr", "runbook", "workflow", "validator", "schema", "architecture_as_code"):
            path = trail.get(key)
            assert path and (ROOT / path).exists(), f"{trail['id']} missing {key}: {path}"
