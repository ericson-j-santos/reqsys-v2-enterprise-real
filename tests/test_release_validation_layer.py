from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.release_validation_layer import (  # noqa: E402
    build_blockers,
    build_ci_semantic_validation,
    consolidate,
    derive_readiness,
    write_report,
)


def coordenador_fixture(state: str = "green", *, critical_gaps: int = 0) -> dict:
    blockers = ["state_yellow"] if state == "yellow" else []
    if state == "red":
        blockers = ["state_red"]
    return {
        "schema_version": "1.3.0",
        "correlation_id": "corr-release-001",
        "generated_at": "2026-06-29T10:00:00Z",
        "state": state,
        "decision": "continuar_proximo_incremento" if state == "green" else "bloquear",
        "increment_gate": {
            "new_front_allowed": state == "green",
            "blockers": blockers,
            "critical_gaps": critical_gaps,
        },
        "sources": {
            "contract_governance": {
                "canonical_drift_count": 0,
                "semantic_drift_count": 0,
                "openapi_validation_passed": True,
            }
        },
        "recommended_actions": [],
    }


def pr_evidence_fixture(status: str = "passed") -> dict:
    return {
        "gate": {
            "status": status,
            "failures": [] if status == "passed" else ["CI — ReqSys v2 Enterprise"],
            "required_workflows": ["CI — ReqSys v2 Enterprise"],
        }
    }


def golden_fixture(score: float = 97.0) -> dict:
    return {
        "score_percent": score,
        "readiness": "ready_with_observation",
        "risk": "low",
        "checks": [{"name": "required_ci_green_policy", "status": "passed", "score": 100}],
    }


def test_consolidate_green_all_sources() -> None:
    report = consolidate(
        "owner/repo",
        "main",
        "123",
        "workflow_dispatch",
        coordenador_fixture("green"),
        pr_evidence_fixture("passed"),
        golden_fixture(98.0),
        {"validation": {"status": "passed"}, "mode": "report_only"},
    )
    assert report["release_readiness_score"] >= 95.0
    assert report["readiness"] in {"ready", "ready_with_observation"}
    assert report["risk"] == "low"
    assert report["operational_state"] == "green"
    assert len(report["quality_gates"]) == 5
    assert report["ci_semantic_validation"]["status"] == "passed"
    assert report["executive_dashboard"]["headline"]


def test_consolidate_blocked_on_red_coordenador() -> None:
    report = consolidate(
        "owner/repo",
        "main",
        "123",
        "schedule",
        coordenador_fixture("red"),
        pr_evidence_fixture("failed"),
        golden_fixture(50.0),
        None,
    )
    assert report["readiness"] == "blocked"
    assert report["risk"] == "high"
    assert "operational_state_red" in report["blockers"]


def test_ci_semantic_validation_warns_on_drift() -> None:
    coordenador = coordenador_fixture("green")
    coordenador["sources"]["contract_governance"]["canonical_drift_count"] = 2
    ci_semantic = build_ci_semantic_validation(coordenador, None, None)
    assert ci_semantic["status"] == "warning"
    assert ci_semantic["canonical_drift_count"] == 2


def test_derive_readiness_with_blockers() -> None:
    assert derive_readiness(99.0, ["operational_state_red"]) == "blocked"
    assert derive_readiness(96.0, []) == "ready"


def test_missing_sources_add_warnings_not_crash() -> None:
    report = consolidate("owner/repo", "main", "1", "local", coordenador_fixture("green"), None, None, None)
    assert any("artifact_missing" in warning for warning in report["warnings"])
    assert report["release_readiness_score"] > 0


def test_write_report_creates_files(tmp_path: Path) -> None:
    report = consolidate(
        "owner/repo",
        "main",
        "1",
        "local",
        coordenador_fixture("green"),
        pr_evidence_fixture("passed"),
        golden_fixture(),
        None,
    )
    write_report(report, tmp_path)
    assert (tmp_path / "release-validation-layer.json").exists()
    assert (tmp_path / "release-validation-layer.md").exists()
    assert (tmp_path / "executive-release-dashboard.json").exists()
    payload = json.loads((tmp_path / "release-validation-layer.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0.0"


def test_build_blockers_critical_gaps() -> None:
    gates = [{"name": "coordenador_operational_state", "status": "yellow", "score": 60}]
    coordenador = coordenador_fixture("yellow", critical_gaps=2)
    ci_semantic = build_ci_semantic_validation(coordenador, None, None)
    blockers = build_blockers(gates, coordenador, ci_semantic)
    assert "critical_gaps" in blockers
