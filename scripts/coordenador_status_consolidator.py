#!/usr/bin/env python3
"""Coordenador Status Consolidator for ReqSys.

Consolida os artifacts 1 e 2 do menu operacional (Operational Governance
Orchestrator + Runtime Health Validator) em um unico coordenador-status.json.
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

STATE_RANK = {"green": 0, "yellow": 1, "red": 2, "unknown": 1}


def merge_state(*states: str) -> str:
    ranked = sorted(states, key=lambda item: STATE_RANK.get(item, 1), reverse=True)
    return ranked[0] if ranked else "unknown"


def build_decision(global_state: str, orchestrator: dict[str, Any], health: dict[str, Any]) -> str:
    if global_state == "red":
        return "bloquear_merges_e_tratar_gaps"
    if global_state == "yellow":
        if orchestrator.get("state") == "yellow":
            return str(orchestrator.get("decision") or "validar_logs_antes_de_merge")
        return "acompanhar_runtime_e_validar_logs"
    return "continuar_proximo_incremento"


def build_executive_status(global_state: str, health: dict[str, Any]) -> str:
    if global_state == "red":
        return "Operacao bloqueada — tratar gaps e falhas reais antes de merge"
    if global_state == "yellow":
        return "Operacao requer acompanhamento — validar pendencias antes de promover"
    return str(health.get("executive_status") or "Operacao saudavel — continuar incremento")


def build_recommended_actions(
    global_state: str,
    orchestrator: dict[str, Any],
    health: dict[str, Any],
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

    if global_state == "green" and not actions:
        actions.append(
            {
                "priority": "P4",
                "action": "continuar_proximo_incremento",
                "reference": "coordenador-menu",
                "detail": "Sem bloqueios — escolher um incremento objetivo",
            }
        )

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
    actions.sort(key=lambda item: priority_order.get(item["priority"], 9))
    return actions


def consolidate(
    repo: str,
    branch: str,
    orchestrator: dict[str, Any],
    health: dict[str, Any],
) -> dict[str, Any]:
    global_state = merge_state(str(orchestrator.get("state") or "unknown"), str(health.get("state") or "unknown"))
    backlog = health.get("automatic_backlog") or []
    critical_gaps = sum(1 for item in backlog if str(item.get("id", "")).startswith("OPS-GAP-"))

    return {
        "schema_version": "1.0.0",
        "correlation_id": str(health.get("correlation_id") or uuid4()),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repo,
        "branch": branch,
        "mode": "report_only",
        "state": global_state,
        "decision": build_decision(global_state, orchestrator, health),
        "executive_status": build_executive_status(global_state, health),
        "operational_score": orchestrator.get("operational_score"),
        "maturity_level": (health.get("maturity") or {}).get("level"),
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
        },
        "automatic_backlog": backlog,
        "recommended_actions": build_recommended_actions(global_state, orchestrator, health),
        "guardrails": {
            "merge": False,
            "deploy": False,
            "production_change": False,
            "branch_protection_change": False,
            "rerun": False,
        },
        "evidence_consolidation": {
            "artifact": "coordenador-status-evidence",
            "files": [
                "coordenador-status.json",
                "summary.md",
                "operational-governance-orchestrator.json",
                "runtime-health-validator.json",
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
        f"- Maturity: `{report['maturity_level']}`",
        f"- Generated at: `{report['generated_at']}`",
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
        lines.append(f"- `{name}`: state=`{source.get('state')}`")

    lines.extend(["", "## Guardrails", ""])
    for key, value in report["guardrails"].items():
        lines.append(f"- `{key}`: `{value}`")

    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_live_reports(
    repo: str,
    branch: str,
    run_limit: int,
    pr_limit: int,
    health_limit: int,
    orchestrator_dir: Path,
    health_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
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

    return orchestrator, health


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.repo and not (args.orchestrator_json and args.health_json):
        print("--repo or GITHUB_REPOSITORY is required unless both JSON inputs are provided", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    orchestrator_dir = output_dir / "sources" / "operational-governance-orchestrator"
    health_dir = output_dir / "sources" / "runtime-health-validator"

    if args.orchestrator_json and args.health_json:
        orchestrator = load_json(Path(args.orchestrator_json))
        health = load_json(Path(args.health_json))
        repo = args.repo or str(orchestrator.get("repository") or "")
        branch = args.branch or str(orchestrator.get("branch") or "main")
    else:
        if not os.environ.get("GITHUB_TOKEN"):
            print("GITHUB_TOKEN is required for live consolidation", file=sys.stderr)
            return 2
        orchestrator, health = fetch_live_reports(
            args.repo,
            args.branch,
            args.run_limit,
            args.pr_limit,
            args.health_limit,
            orchestrator_dir,
            health_dir,
        )
        repo = args.repo
        branch = args.branch

    report = consolidate(repo, branch, orchestrator, health)

    orchestrator_dir.mkdir(parents=True, exist_ok=True)
    health_dir.mkdir(parents=True, exist_ok=True)
    (orchestrator_dir / "operational-governance-orchestrator.json").write_text(
        json.dumps(orchestrator, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (health_dir / "runtime-health-validator.json").write_text(
        json.dumps(health, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    write_report(report, output_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["state"] == "red" else 0


if __name__ == "__main__":
    raise SystemExit(main())
