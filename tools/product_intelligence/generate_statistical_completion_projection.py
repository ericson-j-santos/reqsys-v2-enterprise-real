#!/usr/bin/env python3
"""Generate ReqSys Statistical Completion Projection artifacts.

This generator turns the current executive estimate into deterministic,
review-only artifacts. It does not call external APIs, run agents, deploy,
mutate production, change branches, or write to any external system.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"
DOC_PATH = ROOT / "docs" / "product-intelligence" / "reqsys-statistical-completion-projection.md"

REFERENCE_TIME_BRT = "2026-06-27T21:00:00-03:00"

MATURITY_DIMENSIONS = [
    {"id": "base_architecture", "label": "Arquitetura base", "percent": 88, "maturity": "Alta", "weight": 0.12},
    {"id": "governed_ci_cd", "label": "CI/CD governado", "percent": 82, "maturity": "Alta", "weight": 0.12},
    {"id": "living_architecture", "label": "Living Architecture", "percent": 74, "maturity": "Media/Alta", "weight": 0.10},
    {"id": "observability_analytics", "label": "Observabilidade/Analytics", "percent": 71, "maturity": "Media/Alta", "weight": 0.10},
    {"id": "operational_runtime", "label": "Runtime operacional", "percent": 68, "maturity": "Media", "weight": 0.10},
    {"id": "operational_ux_dashboards", "label": "UX operacional / dashboards", "percent": 72, "maturity": "Media/Alta", "weight": 0.10},
    {"id": "autonomous_automation", "label": "Automacao autonoma", "percent": 63, "maturity": "Media", "weight": 0.10},
    {"id": "enterprise_governance", "label": "Governanca enterprise", "percent": 79, "maturity": "Alta", "weight": 0.12},
    {"id": "environment_sync", "label": "Ambientes sincronizados", "percent": 61, "maturity": "Media", "weight": 0.12},
    {"id": "gold_standard_production", "label": "Producao padrao ouro consolidado", "percent": 54, "maturity": "Media", "weight": 0.10},
]

REAL_COMPLETION_INDICATORS = [
    {"id": "implemented_code", "label": "Codigo implementado", "percent": 78, "weight": 0.16},
    {"id": "validated_code", "label": "Codigo validado", "percent": 69, "weight": 0.14},
    {"id": "operational_evidence", "label": "Evidencia operacional consolidada", "percent": 58, "weight": 0.14},
    {"id": "enterprise_governance", "label": "Governanca enterprise consolidada", "percent": 64, "weight": 0.12},
    {"id": "environment_sync", "label": "Ambientes realmente sincronizados", "percent": 61, "weight": 0.12},
    {"id": "navigable_runtime", "label": "Runtime navegavel/analitico", "percent": 67, "weight": 0.12},
    {"id": "operational_autonomy", "label": "Autonomia operacional", "percent": 55, "weight": 0.10},
    {"id": "total_gold_standard", "label": "Padrao ouro total consolidado", "percent": 52, "weight": 0.10},
]

REMAINING_GAPS = [
    {"id": "runtime_consolidation", "label": "Consolidacao runtime", "gap_percent": 18},
    {"id": "automated_evidence", "label": "Evidencias automatizadas", "gap_percent": 22},
    {"id": "autonomous_operation", "label": "Operacao autonoma", "gap_percent": 31},
    {"id": "total_analytics_drilldown", "label": "Analytics/drill-down total", "gap_percent": 27},
    {"id": "production_hardening", "label": "Hardening producao", "gap_percent": 24},
    {"id": "environment_sync", "label": "Sincronizacao ambientes", "gap_percent": 39},
    {"id": "living_governance", "label": "Governanca viva completa", "gap_percent": 21},
    {"id": "enterprise_operational_ux", "label": "UX operacional enterprise", "gap_percent": 17},
]

VELOCITY = {
    "useful_prs_per_day": {"min": 8, "max": 18},
    "green_merges_per_day": {"min": 6, "max": 14},
    "ci_fixes_per_cycle": {"min": 2, "max": 7},
    "safe_parallel_increments": {"min": 3, "max": 5},
    "pr_to_merge_lead_time_minutes": {"min": 18, "max": 90},
    "ci_stabilization_rate_percent": 83,
    "critical_regression": "Baixa",
    "structural_rework": "Moderado/baixo",
}

PROJECTION_WINDOWS = {
    "current_velocity": [
        {"milestone": "MVP operacional consolidado", "min_days": 3, "max_days": 6},
        {"milestone": "Ambientes sincronizados", "min_days": 5, "max_days": 9},
        {"milestone": "Runtime operacional robusto", "min_days": 7, "max_days": 12},
        {"milestone": "Padrao ouro tecnico", "min_days": 14, "max_days": 22},
        {"milestone": "Padrao ouro consolidado total", "min_days": 21, "max_days": 35},
    ],
    "accelerated": [
        {"milestone": "MVP robusto", "min_days": 2, "max_days": 4},
        {"milestone": "Producao utilizavel forte", "min_days": 5, "max_days": 8},
        {"milestone": "Ambientes quase totalmente sincronizados", "min_days": 4, "max_days": 7},
        {"milestone": "Padrao ouro tecnico", "min_days": 10, "max_days": 16},
        {"milestone": "Consolidacao enterprise completa", "min_days": 14, "max_days": 24},
    ],
}

RISK_INDEX = [
    {"id": "architectural_regression", "label": "Regressao arquitetural", "risk": "Baixo", "weight": 0.12},
    {"id": "branch_collision", "label": "Colisao de branches", "risk": "Medio/Baixo", "weight": 0.10},
    {"id": "ci_instability", "label": "Instabilidade CI", "risk": "Medio", "weight": 0.18},
    {"id": "environment_drift", "label": "Drift entre ambientes", "risk": "Medio", "weight": 0.18},
    {"id": "operational_scalability", "label": "Escalabilidade operacional", "risk": "Medio", "weight": 0.14},
    {"id": "traceability_loss", "label": "Perda de rastreabilidade", "risk": "Baixo", "weight": 0.12},
    {"id": "hidden_coupling", "label": "Acoplamento oculto", "risk": "Medio/Baixo", "weight": 0.16},
]

OUTCOME_PROBABILITIES = [
    {"outcome": "MVP forte em menos de 1 semana", "probability_percent": 87},
    {"outcome": "Producao utilizavel enterprise", "probability_percent": 81},
    {"outcome": "Padrao ouro tecnico real", "probability_percent": 73},
    {"outcome": "Consolidacao enterprise completa", "probability_percent": 61},
]

ACCELERATORS = [
    "ci_auto_healing",
    "automatic_evidence_generation",
    "consolidated_validation_pipeline",
    "flyio_runtime_sync",
    "central_operational_monitor",
    "single_shared_contracts",
    "manual_validation_reduction",
]

BOTTLENECKS = [
    "estabilizacao_continua_ci",
    "sincronizacao_entre_ambientes",
    "evidencia_operacional_automatica",
    "consolidacao_runtime_driven",
    "reducao_acoplamentos_residuais",
    "observabilidade_fim_a_fim",
    "hardening_producao",
]


def weighted_average(items: list[dict[str, Any]], value_key: str = "percent") -> float:
    total_weight = sum(float(item["weight"]) for item in items)
    if total_weight <= 0:
        return 0.0
    return round(sum(float(item[value_key]) * float(item["weight"]) for item in items) / total_weight, 2)


def arithmetic_average(items: list[dict[str, Any]], value_key: str) -> float:
    if not items:
        return 0.0
    return round(sum(float(item[value_key]) for item in items) / len(items), 2)


def range_midpoint(value: dict[str, int]) -> float:
    return round((int(value["min"]) + int(value["max"])) / 2, 2)


def classify_completion(score: float) -> str:
    if score >= 85:
        return "GOLD_STANDARD_READY"
    if score >= 70:
        return "ENTERPRISE_READY_WITH_WARNINGS"
    if score >= 55:
        return "ENTERPRISE_ACCELERATING_WITH_GAPS"
    return "CONSOLIDATION_REQUIRED"


def risk_score(label: str) -> int:
    mapping = {
        "Baixo": 20,
        "Medio/Baixo": 35,
        "Medio": 50,
        "Medio/Alto": 70,
        "Alto": 85,
    }
    return mapping.get(label, 50)


def classify_risk(score: float) -> str:
    if score <= 25:
        return "LOW"
    if score <= 40:
        return "MEDIUM_LOW"
    if score <= 60:
        return "MEDIUM"
    return "HIGH"


def build_projection() -> dict[str, Any]:
    maturity_score = weighted_average(MATURITY_DIMENSIONS)
    real_completion_score = weighted_average(REAL_COMPLETION_INDICATORS)
    average_gap = arithmetic_average(REMAINING_GAPS, "gap_percent")
    weighted_risk_score = round(
        sum(risk_score(item["risk"]) * float(item["weight"]) for item in RISK_INDEX) / sum(float(item["weight"]) for item in RISK_INDEX),
        2,
    )
    bottleneck_priorities = sorted(REMAINING_GAPS, key=lambda item: item["gap_percent"], reverse=True)

    return {
        "schema_version": "1.0.0",
        "projection": "reqsys-statistical-completion-projection",
        "mode": "review_only",
        "reference_time_brt": REFERENCE_TIME_BRT,
        "executive_reading": "Arquitetura enterprise funcional em aceleracao continua; o gargalo principal e consolidacao operacional.",
        "scores": {
            "current_maturity_score": maturity_score,
            "real_completion_score": real_completion_score,
            "average_remaining_gap_percent": average_gap,
            "completion_state": classify_completion(real_completion_score),
            "risk_score": weighted_risk_score,
            "risk_band": classify_risk(weighted_risk_score),
        },
        "current_maturity": MATURITY_DIMENSIONS,
        "real_completion": REAL_COMPLETION_INDICATORS,
        "remaining_gaps": REMAINING_GAPS,
        "velocity": {
            **VELOCITY,
            "useful_prs_per_day_midpoint": range_midpoint(VELOCITY["useful_prs_per_day"]),
            "green_merges_per_day_midpoint": range_midpoint(VELOCITY["green_merges_per_day"]),
            "ci_fixes_per_cycle_midpoint": range_midpoint(VELOCITY["ci_fixes_per_cycle"]),
            "safe_parallel_increments_midpoint": range_midpoint(VELOCITY["safe_parallel_increments"]),
        },
        "bottleneck_priorities": bottleneck_priorities,
        "projection_windows": PROJECTION_WINDOWS,
        "risk_index": RISK_INDEX,
        "outcome_probabilities": OUTCOME_PROBABILITIES,
        "trend": {
            "velocity": "up_strong",
            "maturity": "up_strong",
            "governance": "up_stable",
            "autonomy": "up_moderate",
            "observability": "up_strong",
            "live_runtime": "up_strong",
            "consolidated_production": "up_moderate",
        },
        "accelerators": ACCELERATORS,
        "bottlenecks": BOTTLENECKS,
        "recommended_next_increment": "pipeline-validacao-consolidada-e-evidencias-automaticas",
        "guardrails": {
            "deployment": "disabled",
            "production_mutation": "disabled",
            "external_write": "disabled",
            "agent_execution": "disabled",
            "external_ai_call": "disabled",
            "secret_capture": "disabled",
            "human_review_required": True,
        },
    }


def table_rows(items: list[dict[str, Any]], label_key: str, value_key: str, suffix: str = "%") -> str:
    return "\n".join(f"| {item[label_key]} | {item[value_key]}{suffix} |" for item in items)


def scenario_rows(items: list[dict[str, Any]]) -> str:
    return "\n".join(f"| {item['milestone']} | {item['min_days']}-{item['max_days']} dias |" for item in items)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def build_markdown(payload: dict[str, Any]) -> str:
    scores = payload["scores"]
    gap_rows = table_rows(payload["bottleneck_priorities"], "label", "gap_percent")
    probability_rows = table_rows(payload["outcome_probabilities"], "outcome", "probability_percent")
    accelerators = "\n".join(f"- `{item}`" for item in payload["accelerators"])
    guardrails = "\n".join(f"- `{key}`: `{value}`" for key, value in payload["guardrails"].items())

    return f"""# ReqSys Statistical Completion Projection

## Estado executivo

| Campo | Valor |
|---|---|
| Modo | `{payload['mode']}` |
| Referencia BRT | `{payload['reference_time_brt']}` |
| Estado | `{scores['completion_state']}` |
| Maturidade atual | {scores['current_maturity_score']}% |
| Conclusao real | {scores['real_completion_score']}% |
| Gap medio restante | {scores['average_remaining_gap_percent']}% |
| Risco | `{scores['risk_band']}` ({scores['risk_score']}) |

{payload['executive_reading']}

## Gaps prioritarios

| Area | Gap |
|---|---:|
{gap_rows}

## Projecao por velocidade atual

| Marco | Janela |
|---|---|
{scenario_rows(payload['projection_windows']['current_velocity'])}

## Projecao acelerada

| Marco | Janela |
|---|---|
{scenario_rows(payload['projection_windows']['accelerated'])}

## Probabilidade estatistica

| Resultado | Probabilidade |
|---|---:|
{probability_rows}

## Aceleradores recomendados

{accelerators}

## Guardrails

{guardrails}
"""


def build_html(payload: dict[str, Any]) -> str:
    scores = payload["scores"]
    gap_cards = "".join(
        f"<tr><td>{esc(item['label'])}</td><td>{esc(item['gap_percent'])}%</td></tr>" for item in payload["bottleneck_priorities"]
    )
    probability_rows = "".join(
        f"<tr><td>{esc(item['outcome'])}</td><td>{esc(item['probability_percent'])}%</td></tr>"
        for item in payload["outcome_probabilities"]
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ReqSys Statistical Completion Projection</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1400px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:13px;text-transform:uppercase}}
.metric{{font-size:30px;font-weight:bold;margin-top:8px;color:#38bdf8}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th,td{{padding:12px;border-bottom:1px solid #1f2937;text-align:left}}
.section{{margin-top:28px}}
</style>
</head>
<body>
<div class="container">
<h1>ReqSys Statistical Completion Projection</h1>
<p>Referencia BRT: <strong>{esc(payload['reference_time_brt'])}</strong></p>
<div class="grid">
<div class="card"><div class="label">Estado</div><div class="metric">{esc(scores['completion_state'])}</div></div>
<div class="card"><div class="label">Maturidade</div><div class="metric">{esc(scores['current_maturity_score'])}%</div></div>
<div class="card"><div class="label">Conclusao real</div><div class="metric">{esc(scores['real_completion_score'])}%</div></div>
<div class="card"><div class="label">Risco</div><div class="metric">{esc(scores['risk_band'])}</div></div>
</div>
<div class="section"><h2>Gaps prioritarios</h2><table><tr><th>Area</th><th>Gap</th></tr>{gap_cards}</table></div>
<div class="section"><h2>Probabilidades</h2><table><tr><th>Resultado</th><th>Probabilidade</th></tr>{probability_rows}</table></div>
</div>
</body>
</html>
"""


def write_reports(payload: dict[str, Any], report_dir: Path, doc_path: Path = DOC_PATH) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "reqsys-statistical-completion-projection.json"
    markdown_path = report_dir / "reqsys-statistical-completion-projection.md"
    html_path = report_dir / "reqsys-statistical-completion-projection.html"

    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = build_markdown(payload)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(build_html(payload), encoding="utf-8")

    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(
        markdown
        + "\n## Comando operacional\n\n"
        + "```bash\npython3 tools/product_intelligence/generate_statistical_completion_projection.py reports/product-intelligence\n```\n",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    projection = build_projection()
    write_reports(projection, report_dir)
    scores = projection["scores"]
    print(
        "Statistical completion projection generated: "
        f"{scores['completion_state']} completion={scores['real_completion_score']} risk={scores['risk_band']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
