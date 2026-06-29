from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.agent_increment_gate import resolve_contract_drift_count


def test_strict_flag_exits_one_when_drift_detected(tmp_path: Path) -> None:
    diff_path = tmp_path / "openapi-semantic-diff.json"
    diff_path.write_text(
        json.dumps(
            {
                "status": "drift_detected",
                "summary": {"drift_count": 2},
            }
        ),
        encoding="utf-8",
    )

    status_path = tmp_path / "coordenador-status.json"
    status_path.write_text(
        json.dumps(
            {
                "state": "green",
                "decision": "continuar_proximo_incremento",
                "increment_gate": {
                    "new_front_allowed": True,
                    "allowed_increment_types": ["new_front", "gap_fix", "hotfix", "consolidate"],
                    "blockers": [],
                },
                "recommended_actions": [],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agent_increment_gate.py",
            "--increment-type",
            "new_front",
            "--intent",
            "test strict",
            "--status-json",
            str(status_path),
            "--openapi-semantic-diff-json",
            str(diff_path),
            "--strict",
            "--output-dir",
            str(tmp_path / "gate"),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    payload = json.loads((tmp_path / "gate" / "agent-increment-gate.json").read_text(encoding="utf-8"))
    assert payload["strict_blocked"] is True
    assert payload["contract_drift_count"] == 2


def test_openapi_semantic_diff_strict_exits_one_on_drift(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/openapi_semantic_diff.py",
            "--output",
            str(tmp_path / "diff.json"),
            "--scope",
            "runtime_contract",
            "--strict",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads((tmp_path / "diff.json").read_text(encoding="utf-8"))

    if payload["summary"]["drift_count"] > 0:
        assert completed.returncode == 1
    else:
        assert completed.returncode == 0


def test_resolve_contract_drift_count_reads_coordenador_source() -> None:
    report = {
        "sources": {
            "contract_governance": {
                "semantic_drift_count": 3,
            }
        }
    }
    assert resolve_contract_drift_count(report) == 3
