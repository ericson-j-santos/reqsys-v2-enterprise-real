from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_session_launcher_adoption as adoption


def test_session_launcher_adoption_contract_is_complete():
    assert adoption.validate() == []


def test_session_launcher_adoption_negative_control_detects_missing_snapshot():
    runbook = adoption.RUNBOOK.read_text(encoding="utf-8")
    errors = adoption.validate_text(runbook.replace("snapshot_sha256", ""))
    assert any("snapshot_sha256" in error for error in errors)
