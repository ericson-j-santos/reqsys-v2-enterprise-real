#!/usr/bin/env python3
"""Coordenador Status Consolidator for ReqSys.

Consolida os artifacts 1 e 2 do menu operacional (Operational Governance
Orchestrator + Runtime Health Validator) em um unico coordenador-status.json.
Inclui increment_gate para bloquear novas frentes sem incremento objetivo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STATE_RANK = {"green": 0, "yellow": 1, "red": 2, "unknown": 1}

OPEN_PR_PRESSURE_THRESHOLD = 5

OPERATIONAL_CYCLE = [
    "triagem",
    "ajuste_minimo",
    "ci_completo",
    "evidencia",
    "merge_controlado",
]

INCREMENT_POLICY = (
    "Nao abrir frentes novas sem incremento objetivo. "
    "Ciclo: triagem -> ajuste minimo -> CI -> evidencia -> merge."
)


def merge_state(*states: str) -> str:
    ranked = sorted(states, key=lambda item: STATE_RANK.get(item, 1), reverse=True)
    return ranked[0] if ranked else "unknown"


def _watchdog_result(watchdog: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
    if not watchdog:
        return None
    for item in watchdog.get("results") or []:
        if item.get("name") == name:
            return item
    return None


def _duplicate_groups(watchdog: dict[str, Any] | None) -> list[list[dict[str, Any]]]:
    dup = _watchdog_result(watchdog, "duplicate_open_prs")
    if not dup:
        return []
    return list((dup.get("evidence") or {}).get("duplicate_groups") or [])


def _duplicate_pr_numbers(watchdog: dict[str, Any] | None) -> set[int]:
    numbers: set[int] = set()
    for group in _duplicate_groups(watchdog):
        for pr in group:
            number = pr.get("number")
            if number is not None:
                numbers.add(int(number))
    return numbers


def build_increment_gate(
    global_state: str,
    orchestrator: dict[str, Any],
    health: dict[str, Any],
    watchdog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    backlog = health.get("automatic_backlog") or []
    critical_gaps = sum(1 for item in backlog if str(item.get("id", "")).startswith("OPS-GAP-"))
    open_prs = int((orchestrator.get("summary") or {}).get("open_prs") or 0)
    duplicate_groups = _duplicate_groups(watchdog)

    blockers: list[str] = []
    if global_state == "red":
        blockers.append("state_red")
    if global_state == "yellow":
        blockers.append("state_yellow")
    if critical_gaps > 0:
        blockers.append("critical_gaps")
    if duplicate_groups:
        blockers.append("duplicate_open_prs")
    if open_prs > OPEN_PR_PRESSURE_THRESHOLD:
        blockers.append("open_pr_queue_pressure")

    allowed_types = ["gap_fix", "hotfix", "consolidate"]
    if duplicate_groups:
        allowed_types.append("close_duplicate")
    if not blockers:
        allowed_types.append("new_front")

    return {
        "new_front_allowed": "new_front" in allowed_types and not blockers,
        "blockers": blockers,
        "open_pr_threshold": OPEN_PR_PRESSURE_THRESHOLD,
        "open_prs": open_prs,
        "duplicate_group_count": len(duplicate_groups),
        "critical_gaps": critical_gaps,
        "allowed_increment_types": allowed_types,
        "policy": INCREMENT_POLICY,
    }


def build_decision(
    global_state: str,
    orchestrator: dict[str, Any],
    health: dict[str, Any],
    increment_gate: dict[str, Any],
) -> str:
    if not increment_gate.get("new_front_allowed"):
        if increment_gate.get("blockers"):
            if "critical_gaps" in increment_gate["blockers"] or global_state == "red":
                return "bloquear_novas_frentes_e_tratar_gaps"
            if "duplicate_open_prs" in increment_gate["blockers"]:
                return "consolidar_prs_duplicados_antes_de_novo_incremento"
            if "open_pr_queue_pressure" in increment_gate["blockers"]:
                return "consolidar_fila_pr_antes_de_novo_incremento"
            return "bloquear_novas_frentes_ate_consolidar"
    if global_state == "red":
        return "bloquear_merges_e_tratar_gaps"
    if global_state == "yellow":
        if orchestrator.get("state") == "yellow":
            return str(orchestrator.get("decision") or "validar_logs_antes_de_merge")
        return "acompanhar_runtime_e_validar_logs"
    return "continuar_proximo_incremento"


def build_executive_status(global_state: str, health: dict[str, Any], increment_gate: dict[str, Any]) -> str:
    if not increment_gate.get("new_front_allowed"):
        if "duplicate_open_prs" in increment_gate.get("blockers", []):
            return "Consolidar PRs duplicados antes de abrir nova frente"
        if "open_pr_queue_pressure" in increment_gate.get("blockers", []):
            return "Fila de PRs elevada — concluir incrementos ativos antes de abrir nova frente"
        if increment_gate.get("critical_gaps") or global_state == "red":
            return "Operacao bloqueada — tratar gaps antes de nova frente"
    if global_state == "red":
        return "Operacao bloqueada — tratar gaps e falhas reais antes de merge"
    if global_state == "yellow":
        return "Operacao requer acompanhamento — validar pendencias antes de promover"
    return str(health.get("executive_status") or "Operacao saudavel — continuar incremento")


def build_recommended_actions(
    global_state: str,
    orchestrator: dict[str, Any],
    health: dict[str, Any],
    increment_gate: dict[str, Any],
    watchdog: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    backlog = health.get("automatic_backlog") or []

    for item in backlog:
        item_id = str(item.get("id") or "")
        if item_id.startswith("OPS-GAP-"):
            actions.append(
                {
                    "priority": str(item.get("priority") or "P1"),
                    "action": "abrir_pr_ou_agente_para_correcao",
                    "reference": item_id,
                    "detail": str(item.get("title") or "gap operacional"),
                }
            )
        elif item_id.startswith("OPS-AUTO-"):
            actions.append(
                {
                    "priority": str(item.get("priority") or "P2"),
                    "action": "avaliar_remediacao_allowlisted",
                    "reference": item_id,
                    "detail": "Preferir runtime-health-validator em dry_run antes de execute",
                }
            )
        elif item_id.startswith("OPS-PENDING-"):
            actions.append(
                {
                    "priority": "P3",
                    "action": "aguardar_ou_disparar_pr_ci_watch",
                    "reference": item_id,
                    "detail": str(item.get("title") or "check pendente"),
                }
            )

    for run in orchestrator.get("red_runs") or []:
        actions.append(
            {
                "priority": "P0",
                "action": "investigar_workflow_vermelho",
                "reference": str(run.get("name") or "workflow"),
                "detail": str(run.get("url") or ""),
            }
        )

    for name in orchestrator.get("missing_critical_workflows") or []:
        actions.append(
            {
                "priority": "P2",
                "action": "validar_workflow_ausente_na_janela",
                "reference": str(name),
                "detail": "Disparar leitura ou workflow allowlisted se necessario",
            }
        )

    for group in _duplicate_groups(watchdog):
        numbers = ", ".join(f"#{pr.get('number')}" for pr in group if pr.get("number") is not None)
        actions.append(
            {
                "priority": "P1",
                "action": "fechar_prs_duplicados",
                "reference": numbers or "duplicate_group",
                "detail": "Manter apenas o PR mais recente ou completo por tema",
            }
        )

    if increment_gate.get("blockers") and "open_pr_queue_pressure" in increment_gate["blockers"]:
        actions.append(
            {
                "priority": "P2",
                "action": "consolidar_fila_pr",
                "reference": f"open_prs={increment_gate.get('open_prs')}",
                "detail": (
                    f"Reduzir fila acima de {OPEN_PR_PRESSURE_THRESHOLD} PRs "
                    "antes de incrementos estruturais"
                ),
            }
        )

    if global_state == "green" and increment_gate.get("new_front_allowed") and not actions:
        actions.append(
            {
                "priority": "P4",
                "action": "continuar_proximo_incremento",
                "reference": "coordenador-menu",
                "detail": "Sem bloqueios — escolher um incremento objetivo",
            }
        )

    if not increment_gate.get("new_front_allowed") and not any(
        item["action"] in {"fechar_prs_duplicados", "consolidar_fila_pr"} for item in actions
    ):
        actions.append(
            {
                "priority": "P1",
                "action": "bloquear_nova_frente",
                "reference": ",".join(increment_gate.get("blockers") or []),
                "detail": "Resolver bloqueios antes de abrir branch/PR novo",
            }
        )

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
    actions.sort(key=lambda item: priority_order.get(item["priority"], 9))
    return actions


def _duplicate_numbers_from_report(report: dict[str, Any]) -> set[int]:
    watchdog = report.get("watchdog")
    if isinstance(watchdog, dict):
        return _duplicate_pr_numbers(watchdog)
    source = (report.get("sources") or {}).get("watchdog") or {}
    numbers = source.get("duplicate_pr_numbers") or []
    return {int(number) for number in numbers}


def evaluate_increment_intent(
    report: dict[str, Any],
    increment_type: str,
    reference: str,
) -> tuple[bool, str, str]:
    gate = report.get("increment_gate") or {}
    allowed_types = set(gate.get("allowed_increment_types") or [])
    backlog_ids = {
        str(item.get("id"))
        for item in report.get("automatic_backlog") or []
        if item.get("id")
    }
    duplicate_numbers = _duplicate_numbers_from_report(report)

    if increment_type not in allowed_types:
        blockers = ", ".join(gate.get("blockers") or []) or "condicao operacional"
        return (
            False,
            f"increment_type '{increment_type}' nao permitido",
            f"Bloqueios ativos: {blockers}. Tipos permitidos: {', '.join(sorted(allowed_types)) or 'nenhum'}.",
        )

    if increment_type == "new_front":
        if gate.get("new_front_allowed"):
            return True, "nova_frente_permitida", "Sem bloqueios — prosseguir com incremento objetivo."
        return False, "nova_frente_bloqueada", INCREMENT_POLICY

    if increment_type == "gap_fix":
        if not reference:
            gaps = [item_id for item_id in backlog_ids if item_id.startswith("OPS-GAP-")]
            if not gaps:
                return False, "gap_fix_sem_referencia", "Informe --reference OPS-GAP-* existente no backlog."
            return (
                True,
                "gap_fix_generico",
                f"Referencie um gap explicito. Gaps ativos: {', '.join(sorted(gaps))}.",
            )
        if reference in backlog_ids:
            return True, "gap_fix_referenciado", f"Correcao alinhada ao backlog ({reference})."
        return False, "gap_fix_invalido", f"Referencia {reference} nao encontrada no backlog atual."

    if increment_type == "close_duplicate":
        if not duplicate_numbers:
            return False, "sem_duplicados", "Nenhum grupo de PR duplicado detectado no momento."
        if reference:
            try:
                pr_number = int(reference.lstrip("#"))
            except ValueError:
                return False, "referencia_invalida", "Use --reference com numero de PR duplicado."
            if pr_number not in duplicate_numbers:
                return (
                    False,
                    "pr_nao_duplicado",
                    f"PR #{pr_number} nao esta em grupo duplicado. Duplicados: {sorted(duplicate_numbers)}.",
                )
        return True, "fechar_duplicado_permitido", "Consolidar PRs duplicados e fechar obsoletos."

    if increment_type == "hotfix":
        if reference:
            return True, "hotfix_escopo_fechado", f"Hotfix com referencia {reference}."
        if gate.get("critical_gaps") or report.get("state") == "red":
            return True, "hotfix_emergencial", "Hotfix permitido para tratar falha critica."
        return (
            True,
            "hotfix_generico",
            "Preferir --reference com OPS-GAP-* ou descricao do escopo fechado.",
        )

    if increment_type == "consolidate":
        return (
            True,
            "consolidar_incremento_ativo",
            "Concluir CI/evidencia/merge de incremento ja aberto — nao abre nova frente.",
        )

    return False, "tipo_desconhecido", f"Tipo {increment_type} nao reconhecido."


def consolidate(
    repo: str,
    branch: str,
    orchestrator: dict[str, Any],
    health: dict[str, Any],
    watchdog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    global_state = merge_state(str(orchestrator.get("state") or "unknown"), str(health.get("state") or "unknown"))
    backlog = health.get("automatic_backlog") or []
    critical_gaps = sum(1 for item in backlog if str(item.get("id", "")).startswith("OPS-GAP-"))
    increment_gate = build_increment_gate(global_state, orchestrator, health, watchdog)

    runtime_score = health.get("runtime_score")
    if runtime_score is None:
        runtime_score = (health.get("maturity") or {}).get("score")

    duplicate_numbers = sorted(_duplicate_pr_numbers(watchdog))

    return {
        "schema_version": "1.2.0",
        "correlation_id": str(health.get("correlation_id") or uuid4()),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repo,
        "branch": branch,
        "mode": "report_only",
        "state": global_state,
        "decision": build_decision(global_state, orchestrator, health, increment_gate),
        "executive_status": build_executive_status(global_state, health, increment_gate),
        "operational_cycle": OPERATIONAL_CYCLE,
        "increment_gate": increment_gate,
        "operational_score": orchestrator.get("operational_score"),
        "runtime_score": runtime_score,
        "maturity_level": (health.get("maturity") or {}).get("level"),
        "quarantine": health.get("quarantine") or {"active": False},
        "sources": {
            "orchestrator": {
                "state": orchestrator.get("state"),
                "decision": orchestrator.get("decision"),
                "operational_score": orchestrator.get("operational_score"),
                "generated_at": orchestrator.get("generated_at"),
            },
            "runtime_health": {
                "state": health.get("state"),
                "executive_status": health.get("executive_status"),
                "correlation_id": health.get("correlation_id"),
                "generated_at": health.get("generated_at"),
                "runtime_score": runtime_score,
                "quarantine_active": (health.get("quarantine") or {}).get("active", False),
            },
            "watchdog": {
                "available": watchdog is not None,
                "overall_status": (watchdog or {}).get("overall_status"),
                "duplicate_pr_numbers": duplicate_numbers,
            },
        },
        "summary": {
            "open_prs": (orchestrator.get("summary") or {}).get("open_prs", 0),
            "draft_prs": (orchestrator.get("summary") or {}).get("draft_prs", 0),
            "backlog_items": len(backlog),
            "critical_gaps": critical_gaps,
            "red_workflows": len(orchestrator.get("red_runs") or []),
            "pending_workflows": len(orchestrator.get("pending_runs") or []),
            "missing_critical_workflows": len(orchestrator.get("missing_critical_workflows") or []),
            "regression_state": (health.get("regression_detection") or {}).get("state"),
            "duplicate_pr_groups": increment_gate.get("duplicate_group_count", 0),
            "new_front_allowed": increment_gate.get("new_front_allowed", False),
        },
        "automatic_backlog": backlog,
        "recommended_actions": build_recommended_actions(
            global_state, orchestrator, health, increment_gate, watchdog
        ),
        "guardrails": {
            "merge": False,
            "deploy": False,
            "production_change": False,
            "branch_protection_change": False,
            "rerun": False,
            "new_front": not increment_gate.get("new_front_allowed", True),
        },
        "evidence_consolidation": {
            "artifact": "coordenador-status-evidence",
            "files": [
                "coordenador-status.json",
                "summary.md",
                "operational-governance-orchestrator.json",
                "runtime-health-validator.json",
                "repository-health-report.json",
            ],
            "dashboard_entrypoint": "summary.md",
        },
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "coordenador-status.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Coordenador Status Consolidado",
        "",
        f"- Correlation ID: `{report['correlation_id']}`",
        f"- Repository: `{report['repository']}`",
        f"- Branch: `{report['branch']}`",
        f"- State: `{report['state']}`",
        f"- Decision: `{report['decision']}`",
        f"- Executive status: `{report['executive_status']}`",
        f"- Operational score: `{report['operational_score']}%`",
        f"- Runtime score: `{report.get('runtime_score')}`",
        f"- Maturity: `{report['maturity_level']}`",
        f"- Quarantine active: `{(report.get('quarantine') or {}).get('active', False)}`",
        f"- New front allowed: `{report.get('increment_gate', {}).get('new_front_allowed')}`",
        f"- Generated at: `{report['generated_at']}`",
        "",
        "## Increment gate",
        "",
        f"- Policy: {report.get('increment_gate', {}).get('policy')}",
        f"- Blockers: `{', '.join(report.get('increment_gate', {}).get('blockers') or []) or 'nenhum'}`",
        f"- Allowed types: `{', '.join(report.get('increment_gate', {}).get('allowed_increment_types') or [])}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in report["summary"].items():
        lines.append(f"| `{key}` | `{value}` |")

    lines.extend(["", "## Recommended actions", ""])
    for action in report["recommended_actions"]:
        lines.append(
            f"- `{action['priority']}` · `{action['action']}` · `{action['reference']}` — {action['detail']}"
        )

    lines.extend(["", "## Sources", ""])
    for name, source in report["sources"].items():
        if name == "watchdog":
            lines.append(
                f"- `{name}`: available=`{source.get('available')}` "
                f"duplicates=`{source.get('duplicate_pr_numbers')}`"
            )
        else:
            lines.append(f"- `{name}`: state=`{source.get('state')}`")

    lines.extend(["", "## Guardrails", ""])
    for key, value in report["guardrails"].items():
        lines.append(f"- `{key}`: `{value}`")

    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_watchdog_report(repo: str, token: str) -> dict[str, Any]:
    from dataclasses import asdict

    from scripts.repository_health_watchdog import (  # noqa: PLC0415
        check_duplicate_prs,
        check_main_smoke,
        check_risky_open_prs,
    )

    results = [
        check_main_smoke(repo, token, "Main Smoke CI", "main-smoke-ci-evidence", 24),
        check_duplicate_prs(repo, token),
        check_risky_open_prs(repo, token),
    ]
    critical_failures = [item for item in results if item.severity == "critical" and item.status != "passed"]
    warnings = [item for item in results if item.status == "warning"]
    return {
        "repo": repo,
        "overall_status": "failed" if critical_failures else "warning" if warnings else "passed",
        "results": [asdict(item) for item in results],
    }


def fetch_live_reports(
    repo: str,
    branch: str,
    run_limit: int,
    pr_limit: int,
    health_limit: int,
    orchestrator_dir: Path,
    health_dir: Path,
    include_watchdog: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    from scripts.operational_governance_orchestrator import (  # noqa: PLC0415
        build_report as build_orchestrator_report,
        fetch_open_prs,
        fetch_runs,
        write_report as write_orchestrator_report,
    )
    from scripts.runtime_health_validator import (  # noqa: PLC0415
        build_remediation_plan,
        build_report as build_health_report,
        fetch_recent_runs,
        write_report as write_health_report,
    )

    token = os.environ["GITHUB_TOKEN"]
    runs = fetch_runs(repo, token, branch, run_limit)
    prs = fetch_open_prs(repo, token, pr_limit)
    orchestrator = build_orchestrator_report(repo, branch, runs, prs)
    write_orchestrator_report(orchestrator, orchestrator_dir)

    health_runs = fetch_recent_runs(repo, token, branch, health_limit)
    plan = build_remediation_plan(health_runs)
    health = build_health_report(repo, branch, health_runs, plan, [], "report_only")
    write_health_report(health, health_dir)

    watchdog = build_watchdog_report(repo, token) if include_watchdog else None
    return orchestrator, health, watchdog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolidate coordinator status from artifacts 1 and 2.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--run-limit", type=int, default=50)
    parser.add_argument("--pr-limit", type=int, default=30)
    parser.add_argument("--health-limit", type=int, default=50)
    parser.add_argument("--output-dir", default="artifacts/coordenador-status")
    parser.add_argument("--orchestrator-json", default="", help="Optional existing orchestrator JSON path")
    parser.add_argument("--health-json", default="", help="Optional existing health validator JSON path")
    parser.add_argument("--watchdog-json", default="", help="Optional repository health watchdog JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.repo and not (args.orchestrator_json and args.health_json):
        print("--repo or GITHUB_REPOSITORY is required unless both JSON inputs are provided", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    orchestrator_dir = output_dir / "sources" / "operational-governance-orchestrator"
    health_dir = output_dir / "sources" / "runtime-health-validator"
    watchdog_dir = output_dir / "sources" / "repository-health-watchdog"

    watchdog: dict[str, Any] | None = None
    if args.watchdog_json:
        watchdog = load_json(Path(args.watchdog_json))

    if args.orchestrator_json and args.health_json:
        orchestrator = load_json(Path(args.orchestrator_json))
        health = load_json(Path(args.health_json))
        repo = args.repo or str(orchestrator.get("repository") or "")
        branch = args.branch or str(orchestrator.get("branch") or "main")
    else:
        if not os.environ.get("GITHUB_TOKEN"):
            print("GITHUB_TOKEN is required for live consolidation", file=sys.stderr)
            return 2
        orchestrator, health, live_watchdog = fetch_live_reports(
            args.repo,
            args.branch,
            args.run_limit,
            args.pr_limit,
            args.health_limit,
            orchestrator_dir,
            health_dir,
            include_watchdog=watchdog is None,
        )
        if watchdog is None:
            watchdog = live_watchdog
        repo = args.repo
        branch = args.branch

    report = consolidate(repo, branch, orchestrator, health, watchdog)

    orchestrator_dir.mkdir(parents=True, exist_ok=True)
    health_dir.mkdir(parents=True, exist_ok=True)
    watchdog_dir.mkdir(parents=True, exist_ok=True)
    (orchestrator_dir / "operational-governance-orchestrator.json").write_text(
        json.dumps(orchestrator, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (health_dir / "runtime-health-validator.json").write_text(
        json.dumps(health, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if watchdog is not None:
        (watchdog_dir / "repository-health-report.json").write_text(
            json.dumps(watchdog, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    write_report(report, output_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["state"] == "red" else 0


if __name__ == "__main__":
    raise SystemExit(main())
