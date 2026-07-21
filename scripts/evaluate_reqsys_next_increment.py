#!/usr/bin/env python3
"""Avalia automaticamente o próximo incremento seguro do ReqSys.

O contrato é report-only: não promove ambiente, não faz merge e não altera gates.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_WORKFLOWS = {
    "CI — ReqSys v2 Enterprise",
    "PR Evidence Gate",
    "Governed Merge Queue",
    "Security Baseline Gate",
    "Security Specialized Scanners",
    "Instrumented Executive Readiness",
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def pct(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator * 100, 2)


def latest_runs_by_name(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in sorted(runs, key=lambda item: item.get("created_at", ""), reverse=True):
        name = str(run.get("name") or "")
        if name and name not in latest:
            latest[name] = run
    return latest


def build_report(
    prs: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    readiness: dict[str, Any],
    history: dict[str, Any],
) -> dict[str, Any]:
    latest = latest_runs_by_name(runs)
    required = {name: latest.get(name) for name in sorted(REQUIRED_WORKFLOWS)}
    completed = [run for run in required.values() if run and run.get("status") == "completed"]
    successful = [run for run in completed if run.get("conclusion") == "success"]
    failed = [name for name, run in required.items() if run and run.get("status") == "completed" and run.get("conclusion") == "failure"]
    pending = [name for name, run in required.items() if not run or run.get("status") != "completed"]

    open_prs = [pr for pr in prs if pr.get("state") == "open"]
    mergeable_prs = [pr for pr in open_prs if pr.get("mergeable") is True]
    auto_merge_prs = [pr for pr in open_prs if pr.get("auto_merge_enabled") is True]
    queue_runs = [run for run in runs if run.get("name") == "Governed Merge Queue"]
    queue_active = any(run.get("status") in {"queued", "in_progress", "pending"} for run in queue_runs)

    metric_coverage = readiness.get("metric_coverage_percent")
    readiness_status = readiness.get("status") or "INSUFFICIENT_EVIDENCE"
    eta = history.get("eta") or history.get("milestones") or {}
    history_points = len(history.get("snapshots") or history.get("history") or [])

    ci_stability = pct(len(successful), len(completed))
    parallel_throughput = pct(len(mergeable_prs), len(open_prs))

    blockers: list[str] = []
    if failed:
        blockers.append("required_workflow_failure")
    if pending:
        blockers.append("required_workflows_pending_or_missing")
    if readiness_status in {"INSUFFICIENT_EVIDENCE", "EVIDENCE_INCOMPLETE"}:
        blockers.append("instrumented_readiness_incomplete")
    if open_prs and not mergeable_prs:
        blockers.append("no_mergeable_open_pr")

    if failed:
        next_increment = "remediate_failed_required_workflows"
    elif pending:
        next_increment = "complete_required_workflows"
    elif readiness_status in {"INSUFFICIENT_EVIDENCE", "EVIDENCE_INCOMPLETE"}:
        next_increment = "complete_instrumented_evidence"
    elif history_points < 2:
        next_increment = "accumulate_instrumented_history"
    elif open_prs:
        next_increment = "governed_merge_of_eligible_prs"
    else:
        next_increment = "validate_runtime_deploy_and_smoke"

    ready_for_human_decision = not blockers and readiness_status in {"READY", "CONSOLIDATING"}

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-next-increment-auto-evaluation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "report_only",
        "automatic_promotion_allowed": False,
        "automatic_merge_allowed": False,
        "human_approval_required": True,
        "status": "READY_FOR_HUMAN_DECISION" if ready_for_human_decision else "ACTION_REQUIRED",
        "implemented": True,
        "validated": not failed and not pending,
        "evidenced": bool(runs) and bool(readiness),
        "consolidated": readiness_status in {"READY", "CONSOLIDATING"} and history_points >= 2,
        "production_ready": readiness_status == "READY" and not blockers,
        "merge_queue": {
            "active": queue_active,
            "latest_conclusion": (latest.get("Governed Merge Queue") or {}).get("conclusion"),
        },
        "auto_merge": {
            "enabled_open_prs": len(auto_merge_prs),
            "eligible_mergeable_prs": len(mergeable_prs),
        },
        "ci": {
            "required_total": len(REQUIRED_WORKFLOWS),
            "completed_total": len(completed),
            "successful_total": len(successful),
            "stability_percent": ci_stability,
            "failed": failed,
            "pending_or_missing": pending,
        },
        "integration": {
            "open_prs": len(open_prs),
            "mergeable_open_prs": len(mergeable_prs),
            "parallel_throughput_percent": parallel_throughput,
        },
        "instrumented_metrics": {
            "readiness_status": readiness_status,
            "metric_coverage_percent": metric_coverage,
            "history_points": history_points,
            "eta": eta,
        },
        "human_blockers": blockers,
        "next_safe_increment": next_increment,
    }


def render_markdown(report: dict[str, Any]) -> str:
    ci = report["ci"]
    integration = report["integration"]
    metrics = report["instrumented_metrics"]
    return "\n".join(
        [
            "# Avaliação Automática do Próximo Incremento ReqSys",
            "",
            f"- Status: **{report['status']}**",
            f"- Próximo incremento seguro: **{report['next_safe_increment']}**",
            f"- Estabilidade CI: **{ci['stability_percent']}**",
            f"- Throughput paralelo: **{integration['parallel_throughput_percent']}**",
            f"- Cobertura das métricas: **{metrics['metric_coverage_percent']}**",
            f"- Readiness: **{metrics['readiness_status']}**",
            f"- Pontos históricos: **{metrics['history_points']}**",
            f"- Bloqueios humanos/operacionais: **{', '.join(report['human_blockers']) or 'nenhum'}**",
            "- Modo: **report_only**",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prs", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(
        load_json(args.prs, []),
        load_json(args.runs, []),
        load_json(args.readiness, {}),
        load_json(args.history, {}),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "next": report["next_safe_increment"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
