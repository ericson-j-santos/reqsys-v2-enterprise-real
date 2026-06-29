from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.agent_increment_gate import resolve_contract_drift_count
from scripts.validate_openapi_routes_drift import contract_drift_count


def test_strict_flag_exits_one_when_routes_drift_detected(tmp_path: Path) -> None:
    drift_path = tmp_path / "openapi-routes-drift.json"
    drift_path.write_text(
        json.dumps(
            {
                "status": "failed",
                "summary": {"missing_in_openapi": 2, "missing_in_backend": 0},
                "errors": ["backend_route_missing_in_openapi:GET /api/foo"],
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
            "--openapi-routes-drift-json",
            str(drift_path),
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
    assert payload["canonical_drift_count"] == 2


def test_routes_drift_strict_exits_one_on_failure(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_openapi_routes_drift.py",
            "--contract",
            "docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json",
            "--output",
            str(tmp_path / "drift.json"),
            "--strict",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={
            **os.environ,
            "DATABASE_URL": "sqlite:///./reqsys.db",
            "JWT_SECRET": "ci-placeholder-secret-min-32-chars-long",
            "JWT_ISSUER": "reqsys-ci",
            "JWT_AUDIENCE": "reqsys-ci",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads((tmp_path / "drift.json").read_text(encoding="utf-8"))

    if contract_drift_count(payload) > 0:
        assert completed.returncode == 1
    else:
        assert completed.returncode == 0


def test_resolve_contract_drift_count_prefers_canonical_coordenador_source() -> None:
    report = {
        "sources": {
            "contract_governance": {
                "canonical_drift_count": 3,
                "semantic_drift_count": 9,
            }
        }
    }
    assert resolve_contract_drift_count(report) == 3


def test_semantic_diff_drift_does_not_block_agent_gate_without_routes_drift(tmp_path: Path) -> None:
    semantic_path = tmp_path / "openapi-semantic-diff.json"
    semantic_path.write_text(
        json.dumps({"status": "drift_detected", "summary": {"drift_count": 5}}),
        encoding="utf-8",
    )
    status_path = tmp_path / "coordenador-status.json"
    status_path.write_text(
        json.dumps(
            {
                "state": "green",
                "increment_gate": {
                    "new_front_allowed": True,
                    "allowed_increment_types": ["new_front"],
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
            "--status-json",
            str(status_path),
            "--strict",
            "--output-dir",
            str(tmp_path / "gate"),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
