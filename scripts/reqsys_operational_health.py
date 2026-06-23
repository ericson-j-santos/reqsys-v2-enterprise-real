#!/usr/bin/env python3
"""Generate ReqSys operational health statistics from GitHub PR and workflow data.

Input files are expected to be JSON arrays exported by GitHub CLI.
The script is dependency-free and safe for GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OperationalStatus:
    label: str
    description: str


def load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    raise ValueError(f"Arquivo JSON inválido: {path}. Esperado: lista de objetos.")


def percent(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100, 2)


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def classify(score: float, failure_rate: float, open_prs: int) -> OperationalStatus:
    if score >= 85 and failure_rate <= 10 and open_prs <= 5:
        return OperationalStatus("VERDE", "Operação recente estável, com baixo volume de falhas e baixa fila aberta.")
    if score >= 65 and failure_rate <= 30:
        return OperationalStatus("AMARELO", "Operação aceitável, mas ainda requer acompanhamento e redução de falhas/fila.")
    return OperationalStatus("VERMELHO", "Operação com risco relevante; priorizar estabilização antes de novos incrementos grandes.")


def calculate(prs: list[dict[str, Any]], runs: list[dict[str, Any]]) -> dict[str, Any]:
    total_prs = len(prs)
    open_prs = sum(1 for pr in prs if pr.get("state") == "OPEN" or pr.get("state") == "open")
    merged_prs = sum(1 for pr in prs if pr.get("mergedAt"))
    draft_prs = sum(1 for pr in prs if bool(pr.get("isDraft")))

    total_runs = len(runs)
    success_runs = sum(1 for run in runs if run.get("conclusion") == "success")
    failed_runs = sum(1 for run in runs if run.get("conclusion") in {"failure", "timed_out", "cancelled", "action_required"})
    in_progress_runs = sum(1 for run in runs if run.get("status") in {"queued", "in_progress", "waiting"})

    workflow_success_rate = percent(success_runs, total_runs)
    workflow_failure_rate = percent(failed_runs, total_runs)

    data_confidence_penalty = 0 if total_runs >= 10 else 10
    open_pr_penalty = min(open_prs * 2.5, 20)
    draft_penalty = min(draft_prs * 1.5, 10)
    failure_penalty = min(workflow_failure_rate * 0.7, 45)
    in_progress_penalty = min(in_progress_runs * 1.0, 5)

    score = clamp(100 - data_confidence_penalty - open_pr_penalty - draft_penalty - failure_penalty - in_progress_penalty)
    score = round(score, 2)
    status = classify(score, workflow_failure_rate, open_prs)

    generated_at = datetime.now(timezone.utc).isoformat()

    return {
        "generated_at_utc": generated_at,
        "scope": {
            "prs_analyzed": total_prs,
            "workflow_runs_analyzed": total_runs,
        },
        "prs": {
            "total": total_prs,
            "open": open_prs,
            "draft": draft_prs,
            "merged": merged_prs,
            "merged_rate_percent": percent(merged_prs, total_prs),
        },
        "workflows": {
            "total": total_runs,
            "success": success_runs,
            "failed_or_cancelled": failed_runs,
            "in_progress": in_progress_runs,
            "success_rate_percent": workflow_success_rate,
            "failure_rate_percent": workflow_failure_rate,
        },
        "operational_health": {
            "score_percent": score,
            "status": status.label,
            "description": status.description,
        },
        "limits": [
            "Métricas dependem dos últimos itens retornados pela GitHub API.",
            "Score é indicativo e não substitui inspeção técnica de falhas críticas.",
            "Este script não executa remediação automática.",
        ],
        "recommended_next_actions": build_recommendations(score, workflow_failure_rate, open_prs, draft_prs),
    }


def build_recommendations(score: float, failure_rate: float, open_prs: int, draft_prs: int) -> list[str]:
    recommendations: list[str] = []

    if failure_rate > 20:
        recommendations.append("Priorizar Failure Pattern Engine para classificar falhas recorrentes de CI.")
    if open_prs > 5:
        recommendations.append("Reduzir fila de PRs abertos antes de iniciar incrementos estruturais grandes.")
    if draft_prs > 3:
        recommendations.append("Revisar PRs draft e fechar/atualizar os que não fazem parte da trilha ativa.")
    if score < 65:
        recommendations.append("Congelar novas features e atuar primeiro em estabilização operacional.")
    if not recommendations:
        recommendations.append("Avançar para Operational Center HTML navegável e histórico de tendência.")

    return recommendations


def render_markdown(report: dict[str, Any]) -> str:
    prs = report["prs"]
    workflows = report["workflows"]
    health = report["operational_health"]
    recommendations = report["recommended_next_actions"]
    limits = report["limits"]

    lines = [
        "# ReqSys Operational Health",
        "",
        f"Atualizado em UTC: `{report['generated_at_utc']}`",
        "",
        "## Semáforo operacional",
        "",
        f"**Status:** {health['status']}",
        f"**Score:** {health['score_percent']}%",
        f"**Leitura:** {health['description']}",
        "",
        "## Estatísticas",
        "",
        "| Indicador | Valor |",
        "|---|---:|",
        f"| PRs analisados | {prs['total']} |",
        f"| PRs abertos | {prs['open']} |",
        f"| PRs draft | {prs['draft']} |",
        f"| PRs mergeados | {prs['merged']} |",
        f"| Taxa de PRs mergeados | {prs['merged_rate_percent']}% |",
        f"| Workflow runs analisados | {workflows['total']} |",
        f"| Workflow runs com sucesso | {workflows['success']} |",
        f"| Workflow runs com falha/cancelamento | {workflows['failed_or_cancelled']} |",
        f"| Workflow runs em andamento | {workflows['in_progress']} |",
        f"| Taxa de sucesso de workflows | {workflows['success_rate_percent']}% |",
        f"| Taxa de falha de workflows | {workflows['failure_rate_percent']}% |",
        "",
        "## Próximas ações recomendadas",
        "",
    ]

    lines.extend(f"- {item}" for item in recommendations)
    lines.extend(["", "## Limites operacionais", ""])
    lines.extend(f"- {item}" for item in limits)
    lines.append("")

    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "operational-health.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "operational-health.md").write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ReqSys operational health report.")
    parser.add_argument("--prs", type=Path, required=True, help="Path to PR JSON array.")
    parser.add_argument("--runs", type=Path, required=True, help="Path to workflow runs JSON array.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory.")
    args = parser.parse_args()

    prs = load_json_array(args.prs)
    runs = load_json_array(args.runs)
    report = calculate(prs, runs)
    write_outputs(report, args.out_dir)

    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
