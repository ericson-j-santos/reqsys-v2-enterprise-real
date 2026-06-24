#!/usr/bin/env python3
"""Operational CI Intelligence engine for ReqSys.

Generates an auditable operational report from GitHub Actions run/job data.
It classifies known failures, recommends safe next actions and flags rerun loops.
No destructive or write actions are executed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SEVERITY_WEIGHT = {
    "critical": 100,
    "high": 80,
    "medium": 50,
    "low": 20,
    "info": 5,
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize(value: Any) -> str:
    return str(value or "").lower()


def classify_text(text: str, knowledge_base: dict[str, Any]) -> list[dict[str, Any]]:
    text_norm = normalize(text)
    matches: list[dict[str, Any]] = []
    for item in knowledge_base.get("known_failures", []):
        symptoms = item.get("symptoms", [])
        if any(normalize(symptom) in text_norm for symptom in symptoms):
            matches.append(item)
    return matches


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
    return min(100, sum(SEVERITY_WEIGHT.get(str(match.get("severity", "info")).lower(), 10) for match in matches))


def build_rerun_assessment(runs: list[dict[str, Any]], kb: dict[str, Any]) -> dict[str, Any]:
    policy = kb.get("rerun_policy", {})
    max_without_change = int(policy.get("max_reruns_without_commit_change", 2))
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        key = (str(run.get("workflowName") or run.get("workflow_name") or run.get("name") or "unknown"), str(run.get("headSha") or run.get("head_sha") or "unknown"))
        grouped[key].append(run)

    loops = []
    for (workflow, sha), items in grouped.items():
        attempts = len(items)
        if attempts > max_without_change:
            loops.append({
                "workflow": workflow,
                "head_sha": sha,
                "attempts": attempts,
                "limit": max_without_change,
                "status": "blocked_without_root_cause",
            })

    return {
        "max_reruns_without_commit_change": max_without_change,
        "loops_detected": loops,
        "blocked": len(loops) > 0,
    }


def build_report(runs: list[dict[str, Any]], kb: dict[str, Any]) -> dict[str, Any]:
    classified_runs = []
    all_matches = []

    for run in runs:
        text = collect_text_from_run(run)
        matches = classify_text(text, kb)
        all_matches.extend(matches)
        risk = score_matches(matches)
        classified_runs.append({
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
        })

    category_counter = Counter(match.get("category", "unknown") for match in all_matches)
    severity_counter = Counter(match.get("severity", "unknown") for match in all_matches)
    owner_counter = Counter(match.get("owner", "ci_cd") for match in all_matches)
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

    return {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "operational_score": operational_score,
        "runs_analyzed": len(runs),
        "matches_total": len(all_matches),
        "categories": dict(category_counter),
        "severities": dict(severity_counter),
        "owners": dict(owner_counter),
        "rerun_assessment": rerun,
        "classified_runs": classified_runs,
        "blocked_actions": [
            "auto_merge",
            "auto_fix_in_production",
            "unrestricted_rerun",
            "continue_on_error_to_hide_failure",
        ],
        "recommended_next_actions": recommend_next_actions(status, all_matches, rerun),
    }


def recommend_next_actions(status: str, matches: list[dict[str, Any]], rerun: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    categories = {match.get("category") for match in matches}
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
        "",
        "## Distribuição",
        "",
        "| Dimensão | Dados |",
        "|---|---|",
        f"| Categorias | `{json.dumps(report['categories'], ensure_ascii=False)}` |",
        f"| Severidades | `{json.dumps(report['severities'], ensure_ascii=False)}` |",
        f"| Owners | `{json.dumps(report['owners'], ensure_ascii=False)}` |",
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
    for item in report["classified_runs"]:
        lines.append(
            f"| {item.get('run_id')} | {item.get('workflow')} | {item.get('conclusion')} | {item.get('risk_score')} | {item.get('recommended_owner')} | {item.get('safe_rerun')} |"
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
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-ci-intelligence"))
    args = parser.parse_args()

    runs = load_json(args.runs, [])
    if isinstance(runs, dict):
        runs = runs.get("workflow_runs") or runs.get("runs") or []
    kb = load_json(args.knowledge_base, {})
    report = build_report(runs, kb)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "operational-ci-intelligence.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "operational-ci-intelligence.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
