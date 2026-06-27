from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.coordenador_status_consolidator import (  # noqa: E402
    build_decision,
    consolidate,
    merge_state,
    write_report,
)


def orchestrator_fixture(state: str = "green") -> dict:
    return {
        "schema_version": "1.0.0",
        "generated_at": "2026-06-27T10:00:00Z",
        "repository": "owner/repo",
        "branch": "main",
        "state": state,
        "decision": {
            "green": "continuar_incrementos",
            "yellow": "validar_workflows_ausentes_na_janela_recente",
            "red": "bloquear_novos_merges_e_corrigir_falhas_reais",
        }[state],
        "operational_score": 92.0 if state == "green" else 40.0,
        "summary": {"open_prs": 2, "draft_prs": 1},
        "red_runs": [{"name": "CI Enterprise Fast", "url": "https://example/run/1"}] if state == "red" else [],
        "pending_runs": [],
        "missing_critical_workflows": ["PR CI Watch"] if state == "yellow" else [],
    }


def health_fixture(state: str = "green") -> dict:
    backlog = []
    if state == "red":
        backlog = [
            {
                "id": "OPS-GAP-999",
                "priority": "P0",
                "type": "gap",
                "title": "Falha real em workflow critico",
            }
        ]
    elif state == "yellow":
        backlog = [
            {
                "id": "OPS-PENDING-100",
                "priority": "P3",
                "type": "pending",
                "title": "Check ainda em execucao",
            }
        ]

    return {
        "schema_version": "1.2.0",
        "correlation_id": "corr-test-001",
        "generated_at": "2026-06-27T10:01:00Z",
        "repository": "owner/repo",
        "branch": "main",
        "state": state,
        "executive_status": "Runtime operacional saudavel",
        "runtime_score": 88 if state == "green" else 55,
        "maturity": {"level": "managed" if state == "green" else "defined", "score": 88 if state == "green" else 55},
        "quarantine": {"active": state == "red", "blocked_actions": ["deploy", "promote"] if state == "red" else []},
        "automatic_backlog": backlog,
        "regression_detection": {"state": "regression_suspected" if state == "red" else "no_regression_detected"},
    }


def test_merge_state_prefers_red_over_yellow_and_green() -> None:
    assert merge_state("green", "yellow") == "yellow"
    assert merge_state("yellow", "red") == "red"
    assert merge_state("green", "green") == "green"


def test_consolidate_green_produces_continue_action() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("green"), health_fixture("green"))

    assert report["state"] == "green"
    assert report["decision"] == "continuar_proximo_incremento"
    assert report["runtime_score"] == 88
    assert report["summary"]["critical_gaps"] == 0
    assert report["quarantine"]["active"] is False
    assert any(item["action"] == "continuar_proximo_incremento" for item in report["recommended_actions"])


def test_consolidate_red_blocks_and_surfaces_gaps() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("red"), health_fixture("red"))

    assert report["state"] == "red"
    assert report["decision"] == "bloquear_merges_e_tratar_gaps"
    assert report["quarantine"]["active"] is True
    assert report["summary"]["critical_gaps"] == 1
    assert any(item["reference"] == "OPS-GAP-999" for item in report["recommended_actions"])
    assert any(item["action"] == "investigar_workflow_vermelho" for item in report["recommended_actions"])


def test_consolidate_yellow_uses_orchestrator_decision_when_present() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("yellow"), health_fixture("green"))

    assert report["state"] == "yellow"
    assert report["decision"] == "validar_workflows_ausentes_na_janela_recente"
    assert any(item["action"] == "validar_workflow_ausente_na_janela" for item in report["recommended_actions"])


def test_write_report_publishes_json_and_summary(tmp_path: Path) -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("green"), health_fixture("green"))
    write_report(report, tmp_path)

    payload = json.loads((tmp_path / "coordenador-status.json").read_text(encoding="utf-8"))
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")

    assert payload["schema_version"] == "1.1.0"
    assert payload["runtime_score"] == 88
    assert payload["evidence_consolidation"]["artifact"] == "coordenador-status-evidence"
    assert "## Recommended actions" in summary
    assert build_decision("green", orchestrator_fixture("green"), health_fixture("green")) == "continuar_proximo_incremento"
