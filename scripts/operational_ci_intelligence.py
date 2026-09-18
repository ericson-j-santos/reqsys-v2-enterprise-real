#!/usr/bin/env python3
"""Operational CI Intelligence engine for ReqSys.

Generates an auditable operational report from GitHub Actions run/job data.
It classifies known failures (KB + Failure Pattern Engine), ranks causes via
Pareto analysis, tracks instability history and flags rerun loops.
No destructive or write actions are executed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ci_intelligence_lib import (
    build_instability_snapshot,
    build_pareto_ranking,
    calculate_instability_trend,
    classify_text,
    compute_instability_rate,
    merge_instability_history,
    severity_weight,
)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def collect_text_from_run(run: dict[str, Any]) -> str:
    fragments: list[str] = []
    for key in ["name", "workflowName", "workflow_name", "status", "conclusion", "event", "headBranch", "headSha", "url"]:
        fragments.append(str(run.get(key, "")))
    for job in run.get("jobs", []) or []:
        fragments.extend(str(job.get(key, "")) for key in ["name", "status", "conclusion", "log_excerpt"])
        for step in job.get("steps", []) or []:
            fragments.extend(str(step.get(key, "")) for key in ["name", "status", "conclusion"])
    return "\n".join(fragments)


def infer_owner(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return "ci_cd"
    owners = Counter(match.get("owner", "ci_cd") for match in matches)
    return owners.most_common(1)[0][0]


def score_matches(matches: list[dict[str, Any]]) -> int:
    if not matches:
        return 0
    return min(100, sum(severity_weight(str(match.get("severity", "info"))) for match in matches))


def build_rerun_assessment(runs: list[dict[str, Any]], kb: dict[str, Any]) -> dict[str, Any]:
    policy = kb.get("rerun_policy", {})
    max_without_change = int(policy.get("max_reruns_without_commit_change", 2))
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        key = (
            str(run.get("workflowName") or run.get("workflow_name") or run.get("name") or "unknown"),
            str(run.get("headSha") or run.get("head_sha") or "unknown"),
        )
        grouped[key].append(run)

    loops = []
    for (workflow, sha), items in grouped.items():
        attempts = len(items)
        if attempts > max_without_change:
            loops.append(
                {
                    "workflow": workflow,
                    "head_sha": sha,
                    "attempts": attempts,
                    "limit": max_without_change,
                    "status": "blocked_without_root_cause",
                }
            )

    return {
        "max_reruns_without_commit_change": max_without_change,
        "loops_detected": loops,
        "blocked": len(loops) > 0,
    }


def build_report(
    runs: list[dict[str, Any]],
    kb: dict[str, Any],
    catalog: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    max_history_items: int = 120,
) -> dict[str, Any]:
    classified_runs = []
    all_matches = []

    for run in runs:
        text = collect_text_from_run(run)
        matches = classify_text(text, kb, catalog)
        all_matches.extend(matches)
        risk = score_matches(matches)
        classified_runs.append(
            {
                "run_id": run.get("databaseId") or run.get("id") or run.get("run_id"),
                "workflow": run.get("workflowName") or run.get("workflow_name") or run.get("name"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "head_sha": run.get("headSha") or run.get("head_sha"),
                "url": run.get("url") or run.get("html_url"),
                "matches": matches,
                "risk_score": risk,
                "recommended_owner": infer_owner(matches),
                "safe_rerun": bool(matches) and all(bool(match.get("safe_rerun", False)) for match in matches),
            }
        )

    category_counter = Counter(match.get("category", "unknown") for match in all_matches)
    severity_counter = Counter(match.get("severity", "unknown") for match in all_matches)
    owner_counter = Counter(match.get("owner", "ci_cd") for match in all_matches)
    source_counter = Counter(match.get("source", "unknown") for match in all_matches)
    rerun = build_rerun_assessment(runs, kb)
    max_run_risk = max((item["risk_score"] for item in classified_runs), default=0)
    recurrence_penalty = min(len(all_matches) * 5, 25)
    loop_penalty = 25 if rerun["blocked"] else 0
    operational_score = max(0, 100 - max_run_risk - recurrence_penalty - loop_penalty)

    if operational_score >= 85:
        status = "VERDE"
    elif operational_score >= 65:
        status = "AMARELO"
    else:
        status = "VERMELHO"

    instability = compute_instability_rate(runs)
    pareto = build_pareto_ranking(classified_runs)

    report_core = {
        "schema_version": "1.1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "operational_score": operational_score,
        "runs_analyzed": len(runs),
        "matches_total": len(all_matches),
        "categories": dict(category_counter),
        "severities": dict(severity_counter),
        "owners": dict(owner_counter),
        "classification_sources": dict(source_counter),
        "instability": instability,
        "pareto_failures": pareto,
        "rerun_assessment": rerun,
        "classified_runs": classified_runs,
        "blocked_actions": [
            "auto_merge",
            "auto_fix_in_production",
            "unrestricted_rerun",
            "continue_on_error_to_hide_failure",
        ],
        "recommended_next_actions": recommend_next_actions(status, all_matches, rerun, pareto),
    }

    snapshot = build_instability_snapshot(report_core, instability, pareto)
    merged_history = merge_instability_history(history or [], snapshot, max_history_items)
    trend = calculate_instability_trend(merged_history)
    report_core["instability_history"] = {
        "snapshot": snapshot,
        "trend": trend,
        "points": len(merged_history),
        "history": merged_history,
    }
    return report_core


def recommend_next_actions(
    status: str,
    matches: list[dict[str, Any]],
    rerun: dict[str, Any],
    pareto: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    categories = {match.get("category") for match in matches}
    top_causes = pareto.get("top_causes", [])
    if top_causes:
        top = top_causes[0]
        actions.append(
            f"Priorizar Pareto tier A: {top.get('name')} ({top.get('category')}) — "
            f"{top.get('occurrences')} ocorrência(s), impacto {top.get('impact_score')}."
        )
    if rerun.get("blocked"):
        actions.append("Bloquear novo rerun ate existir mudanca de commit ou causa raiz documentada.")
    if "security" in categories:
        actions.append("Tratar falha de seguranca como bloqueio real e abrir PR corretivo.")
    if "test_failure" in categories:
        actions.append("Corrigir regressao de teste antes de qualquer rerun adicional.")
    if "permissions" in categories:
        actions.append("Revisar permissions do workflow e escopos do GITHUB_TOKEN.")
    if "artifact" in categories:
        actions.append("Validar nomenclatura, retention e ordem de publicacao dos artifacts.")
    if not actions:
        actions.append("Manter monitoramento e consolidar historico para tendencia/MTTR.")
    if status == "VERMELHO":
        actions.insert(0, "Congelar novos incrementos grandes ate estabilizar CI operacional.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    instability = report.get("instability", {})
    pareto = report.get("pareto_failures", {})
    history = report.get("instability_history", {})
    trend = history.get("trend", {})

    lines = [
        "# Operational CI Intelligence",
        "",
        f"Atualizado em UTC: `{report['generated_at_utc']}`",
        "",
        "## Semáforo operacional",
        "",
        f"**Status:** {report['status']}",
        f"**Score operacional:** {report['operational_score']}%",
        f"**Runs analisados:** {report['runs_analyzed']}",
        f"**Matches:** {report['matches_total']}",
        f"**Taxa de instabilidade:** {instability.get('rate_percent', 0)}%",
        "",
        "## Pareto de falhas",
        "",
        "| Causa | Categoria | Tier | Ocorrências | Impacto | Acumulado |",
        "|---|---|---|---:|---:|---:|",
    ]
    for item in pareto.get("top_causes", [])[:8]:
        lines.append(
            f"| {item.get('name')} | {item.get('category')} | {item.get('pareto_tier')} | "
            f"{item.get('occurrences')} | {item.get('impact_score')} | {item.get('cumulative_percent')}% |"
        )

    lines.extend(
        [
            "",
            "## Histórico de instabilidade",
            "",
            f"- Direção: `{trend.get('direction', 'unknown')}`",
            f"- Delta instabilidade: `{trend.get('delta_instability', 0)}%`",
            f"- Pontos históricos: `{history.get('points', 0)}`",
            f"- Média instabilidade: `{trend.get('avg_instability_rate', 0)}%`",
            "",
            "## Distribuição",
            "",
            "| Dimensão | Dados |",
            "|---|---|",
            f"| Categorias | `{json.dumps(report['categories'], ensure_ascii=False)}` |",
            f"| Severidades | `{json.dumps(report['severities'], ensure_ascii=False)}` |",
            f"| Owners | `{json.dumps(report['owners'], ensure_ascii=False)}` |",
            f"| Fontes de classificação | `{json.dumps(report.get('classification_sources', {}), ensure_ascii=False)}` |",
            "",
            "## Anti-rerun infinito",
            "",
            f"- Bloqueado: `{report['rerun_assessment']['blocked']}`",
            f"- Limite: `{report['rerun_assessment']['max_reruns_without_commit_change']}` reruns sem mudança de commit",
            "",
            "## Runs classificados",
            "",
            "| Run | Workflow | Conclusão | Risco | Owner | Rerun seguro |",
            "|---|---|---|---:|---|---|",
        ]
    )
    for item in report["classified_runs"]:
        lines.append(
            f"| {item.get('run_id')} | {item.get('workflow')} | {item.get('conclusion')} | "
            f"{item.get('risk_score')} | {item.get('recommended_owner')} | {item.get('safe_rerun')} |"
        )
    lines.extend(["", "## Próximas ações recomendadas", ""])
    lines.extend(f"- {action}" for action in report["recommended_next_actions"])
    lines.extend(["", "## Ações bloqueadas", ""])
    lines.extend(f"- `{action}`" for action in report["blocked_actions"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Operational CI Intelligence report.")
    parser.add_argument("--runs", type=Path, required=True, help="JSON file with run list.")
    parser.add_argument("--knowledge-base", type=Path, default=Path("config/ci-failure-knowledge-base.json"))
    parser.add_argument("--failure-patterns", type=Path, default=Path("config/failure-patterns.json"))
    parser.add_argument("--history", type=Path, default=Path("data/operational-ci-history/instability-history.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-ci-intelligence"))
    parser.add_argument("--max-history-items", type=int, default=120)
    args = parser.parse_args()

    runs = load_json(args.runs, [])
    if isinstance(runs, dict):
        runs = runs.get("workflow_runs") or runs.get("runs") or []
    kb = load_json(args.knowledge_base, {})
    catalog = load_json(args.failure_patterns, {})
    existing_history = load_json(args.history, [])
    if not isinstance(existing_history, list):
        existing_history = []

    report = build_report(
        runs if isinstance(runs, list) else [],
        kb,
        catalog=catalog,
        history=existing_history,
        max_history_items=args.max_history_items,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    history_path = args.history
    history_path.parent.mkdir(parents=True, exist_ok=True)
    merged_history = report["instability_history"]["history"]
    history_path.write_text(json.dumps(merged_history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (args.out_dir / "operational-ci-intelligence.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.out_dir / "operational-ci-intelligence.md").write_text(render_markdown(report), encoding="utf-8")
    (args.out_dir / "instability-history.json").write_text(
        json.dumps(merged_history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
