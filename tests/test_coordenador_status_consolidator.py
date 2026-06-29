from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.agent_increment_gate import main as gate_main  # noqa: E402
from scripts.coordenador_status_consolidator import (  # noqa: E402
    build_contract_governance_source,
    build_increment_gate,
    consolidate,
    evaluate_increment_intent,
    merge_state,
    write_report,
)


def orchestrator_fixture(state: str = "green", open_prs: int = 2) -> dict:
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
        "summary": {"open_prs": open_prs, "draft_prs": 1},
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


def watchdog_fixture(*, duplicates: bool = False) -> dict:
    duplicate_groups = (
        [
            [
                {"number": 10, "title": "feat X", "draft": False},
                {"number": 11, "title": "feat X", "draft": True},
            ]
        ]
        if duplicates
        else []
    )
    return {
        "repo": "owner/repo",
        "overall_status": "warning" if duplicates else "passed",
        "results": [
            {
                "name": "duplicate_open_prs",
                "status": "warning" if duplicates else "passed",
                "severity": "medium" if duplicates else "info",
                "evidence": {"duplicate_groups": duplicate_groups},
                "recommendation": "Fechar duplicados" if duplicates else "OK",
            }
        ],
    }


def test_merge_state_prefers_red_over_yellow_and_green() -> None:
    assert merge_state("green", "yellow") == "yellow"
    assert merge_state("yellow", "red") == "red"
    assert merge_state("green", "green") == "green"


def test_consolidate_green_produces_continue_action() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("green"), health_fixture("green"))

    assert report["state"] == "green"
    assert report["decision"] == "continuar_proximo_incremento"
    assert report["increment_gate"]["new_front_allowed"] is True
    assert report["summary"]["critical_gaps"] == 0
    assert report["guardrails"]["new_front"] is False
    assert any(item["action"] == "continuar_proximo_incremento" for item in report["recommended_actions"])


def test_consolidate_red_blocks_new_front() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("red"), health_fixture("red"))

    assert report["state"] == "red"
    assert report["decision"] == "bloquear_novas_frentes_e_tratar_gaps"
    assert report["increment_gate"]["new_front_allowed"] is False
    assert report["guardrails"]["new_front"] is True
    assert any(item["reference"] == "OPS-GAP-999" for item in report["recommended_actions"])


def test_consolidate_duplicate_prs_blocks_new_front() -> None:
    report = consolidate(
        "owner/repo",
        "main",
        orchestrator_fixture("green"),
        health_fixture("green"),
        watchdog_fixture(duplicates=True),
    )

    assert report["increment_gate"]["new_front_allowed"] is False
    assert report["decision"] == "consolidar_prs_duplicados_antes_de_novo_incremento"
    assert any(item["action"] == "fechar_prs_duplicados" for item in report["recommended_actions"])


def test_increment_gate_open_pr_pressure() -> None:
    gate = build_increment_gate(
        "green",
        orchestrator_fixture("green", open_prs=8),
        health_fixture("green"),
        None,
    )
    assert "open_pr_queue_pressure" in gate["blockers"]
    assert gate["new_front_allowed"] is False


def test_evaluate_increment_intent_blocks_new_front_when_red() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("red"), health_fixture("red"))
    allowed, reason, _ = evaluate_increment_intent(report, "new_front", "")
    assert allowed is False
    assert "new_front" in reason


def test_evaluate_increment_intent_allows_gap_fix_with_reference() -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("red"), health_fixture("red"))
    allowed, reason, _ = evaluate_increment_intent(report, "gap_fix", "OPS-GAP-999")
    assert allowed is True
    assert reason == "gap_fix_referenciado"


def test_evaluate_increment_intent_allows_close_duplicate() -> None:
    report = consolidate(
        "owner/repo",
        "main",
        orchestrator_fixture("green"),
        health_fixture("green"),
        watchdog_fixture(duplicates=True),
    )
    allowed, _, _ = evaluate_increment_intent(report, "close_duplicate", "10")
    assert allowed is True


def test_write_report_publishes_json_and_summary(tmp_path: Path) -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("green"), health_fixture("green"))
    write_report(report, tmp_path)

    payload = json.loads((tmp_path / "coordenador-status.json").read_text(encoding="utf-8"))
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")

    assert payload["schema_version"] == "1.2.0"
    assert payload["increment_gate"]["new_front_allowed"] is True
    assert "## Increment gate" in summary


def test_agent_increment_gate_cli_blocks_new_front_on_red(tmp_path: Path) -> None:
    report = consolidate("owner/repo", "main", orchestrator_fixture("red"), health_fixture("red"))
    status_path = tmp_path / "coordenador-status.json"
    status_path.write_text(json.dumps(report), encoding="utf-8")

    exit_code = gate_main(
        [
            "--increment-type",
            "new_front",
            "--status-json",
            str(status_path),
            "--output-dir",
            str(tmp_path / "gate"),
        ]
    )
    assert exit_code == 1


def test_consolidator_cli_exits_zero_on_red_without_fail_on_red(tmp_path: Path) -> None:
    import subprocess

    orchestrator_path = tmp_path / "orchestrator.json"
    health_path = tmp_path / "health.json"
    output_dir = tmp_path / "out"
    orchestrator_path.write_text(json.dumps(orchestrator_fixture("red")), encoding="utf-8")
    health_path.write_text(json.dumps(health_fixture("red")), encoding="utf-8")

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "scripts" / "coordenador_status_consolidator.py"),
            "--orchestrator-json",
            str(orchestrator_path),
            "--health-json",
            str(health_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads((output_dir / "coordenador-status.json").read_text(encoding="utf-8"))
    assert payload["state"] == "red"


def test_consolidator_cli_exits_one_on_red_with_fail_on_red(tmp_path: Path) -> None:
    import subprocess

    orchestrator_path = tmp_path / "orchestrator.json"
    health_path = tmp_path / "health.json"
    output_dir = tmp_path / "out"
    orchestrator_path.write_text(json.dumps(orchestrator_fixture("red")), encoding="utf-8")
    health_path.write_text(json.dumps(health_fixture("red")), encoding="utf-8")

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "scripts" / "coordenador_status_consolidator.py"),
            "--orchestrator-json",
            str(orchestrator_path),
            "--health-json",
            str(health_path),
            "--output-dir",
            str(output_dir),
            "--fail-on-red",
        ],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1, completed.stderr


def test_consolidator_cli_imports_without_pythonpath(tmp_path: Path) -> None:
    import subprocess

    orchestrator_path = tmp_path / "orchestrator.json"
    health_path = tmp_path / "health.json"
    output_dir = tmp_path / "out"
    orchestrator_path.write_text(json.dumps(orchestrator_fixture("green")), encoding="utf-8")
    health_path.write_text(json.dumps(health_fixture("green")), encoding="utf-8")

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "scripts" / "coordenador_status_consolidator.py"),
            "--orchestrator-json",
            str(orchestrator_path),
            "--health-json",
            str(health_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads((output_dir / "coordenador-status.json").read_text(encoding="utf-8"))
    assert payload["state"] == "green"


def test_build_contract_governance_source_summarizes_drift() -> None:
    source = build_contract_governance_source(
        {
            "version": "0.3.0",
            "status": "governed",
            "summary": {"runtime_contract_sync": "partial"},
            "traceability": {"openapi_to_ci": {"gap": "semantic_backend_route_sync_pending"}},
            "artifacts": [{"name": "OpenAPI"}],
        },
        {"status": "passed", "summary": {"valid": True}},
        {"status": "failed", "summary": {"missing_in_openapi": 2, "missing_in_backend": 0}},
        {"status": "drift_detected", "summary": {"drift_count": 5, "missing_in_openapi": 5}},
    )

    assert source["available"] is True
    assert source["canonical_drift_count"] == 2
    assert source["semantic_drift_count"] == 5
    assert source["canonical_drift_detector"] == "reqsys-openapi-routes-drift"
    assert source["sync_gap"] == "semantic_backend_route_sync_pending"


def test_consolidate_includes_contract_governance_without_blocking_increment_gate() -> None:
    contract_governance = build_contract_governance_source(
        {"version": "0.3.0", "summary": {}, "traceability": {}, "artifacts": []},
        {"status": "passed", "summary": {"valid": True}},
        {"status": "failed", "summary": {"missing_in_openapi": 3, "missing_in_backend": 0}},
        {"status": "drift_detected", "summary": {"drift_count": 9, "missing_in_openapi": 9}},
    )
    report = consolidate(
        "owner/repo",
        "main",
        orchestrator_fixture("green"),
        health_fixture("green"),
        contract_governance=contract_governance,
    )

    assert report["increment_gate"]["new_front_allowed"] is True
    assert report["summary"]["contract_governance_available"] is True
    assert report["summary"]["openapi_canonical_drift_count"] == 3
    assert report["summary"]["openapi_semantic_drift_count"] == 9
    assert report["sources"]["contract_governance"]["canonical_drift_count"] == 3
    assert any(
        item["action"] == "sincronizar_contrato_openapi_backend"
        for item in report["recommended_actions"]
    )
