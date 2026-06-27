#!/usr/bin/env python3
"""Generate ReqSys completion statistical projection artifacts.

The projection is a deterministic, review-only snapshot from the executive
reference supplied for 2026-06-27 21:00 BRT. It does not query GitHub, deploy,
mutate production, call external services or execute agents.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "product-intelligence"

REFERENCE_TIMESTAMP = "2026-06-27T21:00:00-03:00"
REFERENCE_LABEL = "27/06/2026 21:00 BRT"

CURRENT_STATE = [
    {"dimension": "Arquitetura base", "percent": 88, "maturity": "Alta"},
    {"dimension": "CI/CD governado", "percent": 82, "maturity": "Alta"},
    {"dimension": "Living Architecture", "percent": 74, "maturity": "Média/Alta"},
    {"dimension": "Observabilidade/Analytics", "percent": 71, "maturity": "Média/Alta"},
    {"dimension": "Runtime operacional", "percent": 68, "maturity": "Média"},
    {"dimension": "UX operacional / dashboards", "percent": 72, "maturity": "Média/Alta"},
    {"dimension": "Automação autônoma", "percent": 63, "maturity": "Média"},
    {"dimension": "Governança enterprise", "percent": 79, "maturity": "Alta"},
    {"dimension": "Ambientes sincronizados", "percent": 61, "maturity": "Média"},
    {"dimension": "Produção padrão ouro consolidado", "percent": 54, "maturity": "Média"},
]

VELOCITY = [
    {"metric": "PRs/dia úteis", "low": 8, "high": 18, "unit": "prs_per_business_day"},
    {"metric": "Merges verdes/dia", "low": 6, "high": 14, "unit": "green_merges_per_day"},
    {"metric": "Correções CI por ciclo", "low": 2, "high": 7, "unit": "ci_fixes_per_cycle"},
    {"metric": "Incrementos paralelos seguros", "low": 3, "high": 5, "unit": "safe_parallel_increments"},
    {"metric": "Lead time médio PR para merge", "low": 18, "high": 90, "unit": "minutes"},
]

COMPLETION_INDICATORS = [
    {"indicator": "Código implementado", "percent": 78},
    {"indicator": "Código validado", "percent": 69},
    {"indicator": "Evidência operacional consolidada", "percent": 58},
    {"indicator": "Governança enterprise consolidada", "percent": 64},
    {"indicator": "Ambientes realmente sincronizados", "percent": 61},
    {"indicator": "Runtime navegável/analítico", "percent": 67},
    {"indicator": "Autonomia operacional", "percent": 55},
    {"indicator": "Padrão ouro total consolidado", "percent": 52},
]

REMAINING_GAPS = [
    {"area": "Consolidação runtime", "gap_percent": 18},
    {"area": "Evidências automatizadas", "gap_percent": 22},
    {"area": "Operação autônoma", "gap_percent": 31},
    {"area": "Analytics/drill-down total", "gap_percent": 27},
    {"area": "Hardening produção", "gap_percent": 24},
    {"area": "Sincronização ambientes", "gap_percent": 39},
    {"area": "Governança viva completa", "gap_percent": 21},
    {"area": "UX operacional enterprise", "gap_percent": 17},
]

CONSERVATIVE_MILESTONES = [
    {"milestone": "MVP operacional consolidado", "low_days": 3, "high_days": 6},
    {"milestone": "Ambientes sincronizados", "low_days": 5, "high_days": 9},
    {"milestone": "Runtime operacional robusto", "low_days": 7, "high_days": 12},
    {"milestone": "Padrão ouro técnico", "low_days": 14, "high_days": 22},
    {"milestone": "Padrão ouro consolidado total", "low_days": 21, "high_days": 35},
]

ACCELERATED_MILESTONES = [
    {"milestone": "MVP robusto", "low_days": 2, "high_days": 4},
    {"milestone": "Produção utilizável forte", "low_days": 5, "high_days": 8},
    {"milestone": "Ambientes quase totalmente sincronizados", "low_days": 4, "high_days": 7},
    {"milestone": "Padrão ouro técnico", "low_days": 10, "high_days": 16},
    {"milestone": "Consolidação enterprise completa", "low_days": 14, "high_days": 24},
]

RISKS = [
    {"type": "Regressão arquitetural", "risk": "Baixo"},
    {"type": "Colisão de branches", "risk": "Médio/Baixo"},
    {"type": "Instabilidade CI", "risk": "Médio"},
    {"type": "Drift entre ambientes", "risk": "Médio"},
    {"type": "Escalabilidade operacional", "risk": "Médio"},
    {"type": "Perda de rastreabilidade", "risk": "Baixo"},
    {"type": "Acoplamento oculto", "risk": "Médio/Baixo"},
]

TRENDS = [
    {"indicator": "Velocidade", "trend": "Forte alta"},
    {"indicator": "Maturidade", "trend": "Forte alta"},
    {"indicator": "Governança", "trend": "Alta estável"},
    {"indicator": "Autonomia", "trend": "Alta moderada"},
    {"indicator": "Observabilidade", "trend": "Forte alta"},
    {"indicator": "Runtime vivo", "trend": "Forte alta"},
    {"indicator": "Produção consolidada", "trend": "Alta moderada"},
]

FINAL_PROBABILITIES = [
    {"outcome": "MVP forte em menos de 1 semana", "probability_percent": 87},
    {"outcome": "Produção utilizável enterprise", "probability_percent": 81},
    {"outcome": "Padrão ouro técnico real", "probability_percent": 73},
    {"outcome": "Consolidação enterprise completa", "probability_percent": 61},
]

BOTTLENECKS = [
    "estabilização contínua de CI",
    "sincronização entre ambientes",
    "evidência operacional automática",
    "consolidação runtime-driven",
    "redução de acoplamentos residuais",
    "observabilidade fim-a-fim",
    "hardening de produção",
]

ACCELERATORS = [
    "CI auto-healing",
    "geração automática de evidências",
    "pipeline de validação consolidada",
    "sincronização Fly.io/runtime",
    "monitor operacional centralizado",
    "contratos/shared packages únicos",
    "redução de validações manuais",
]

RISK_SCORE = {"Baixo": 25, "Médio/Baixo": 40, "Médio": 55, "Médio/Alta": 70, "Alto": 85}


def average(items: list[dict[str, Any]], key: str) -> float:
    return round(sum(float(item[key]) for item in items) / len(items), 2)


def midpoint(low: float, high: float) -> float:
    return round((low + high) / 2, 2)


def with_midpoint(item: dict[str, Any], low_key: str, high_key: str, midpoint_key: str) -> dict[str, Any]:
    enriched = dict(item)
    enriched[midpoint_key] = midpoint(float(item[low_key]), float(item[high_key]))
    return enriched


def risk_band(score: float) -> str:
    if score < 35:
        return "LOW"
    if score < 50:
        return "MEDIUM_LOW"
    if score < 70:
        return "MEDIUM"
    return "HIGH"


def build_projection() -> dict[str, Any]:
    velocity = [with_midpoint(item, "low", "high", "midpoint") for item in VELOCITY]
    conservative = [with_midpoint(item, "low_days", "high_days", "midpoint_days") for item in CONSERVATIVE_MILESTONES]
    accelerated = [with_midpoint(item, "low_days", "high_days", "midpoint_days") for item in ACCELERATED_MILESTONES]

    risk_score = average(
        [{"risk_score": RISK_SCORE[item["risk"]]} for item in RISKS],
        "risk_score",
    )
    implemented = next(item["percent"] for item in COMPLETION_INDICATORS if item["indicator"] == "Código implementado")
    validated = next(item["percent"] for item in COMPLETION_INDICATORS if item["indicator"] == "Código validado")
    gold_total = next(item["percent"] for item in COMPLETION_INDICATORS if item["indicator"] == "Padrão ouro total consolidado")

    return {
        "schema_version": "1.0.0",
        "projection": "reqsys-completion-statistical-projection",
        "mode": "review_only",
        "reference_timestamp": REFERENCE_TIMESTAMP,
        "reference_label": REFERENCE_LABEL,
        "current_state": CURRENT_STATE,
        "velocity": {
            "observed": velocity,
            "ci_stabilization_rate_percent": 83,
            "critical_regression": "Baixa",
            "structural_rework": "Moderado/baixo",
        },
        "completion_indicators": COMPLETION_INDICATORS,
        "remaining_gaps": REMAINING_GAPS,
        "milestones": {
            "conservative": conservative,
            "accelerated": accelerated,
        },
        "bottlenecks": BOTTLENECKS,
        "risks": RISKS,
        "trends": TRENDS,
        "final_probabilities": FINAL_PROBABILITIES,
        "accelerators": ACCELERATORS,
        "statistical_summary": {
            "ecosystem_maturity_percent": average(CURRENT_STATE, "percent"),
            "real_completion_percent": average(COMPLETION_INDICATORS, "percent"),
            "remaining_gap_percent": average(REMAINING_GAPS, "gap_percent"),
            "implemented_to_validated_gap_pp": implemented - validated,
            "gold_standard_completion_percent": gold_total,
            "gold_standard_gap_percent": 100 - gold_total,
            "risk_score_percent": risk_score,
            "risk_band": risk_band(risk_score),
            "probability_index_percent": average(FINAL_PROBABILITIES, "probability_percent"),
            "mvp_acceleration_gain_days": round(conservative[0]["midpoint_days"] - accelerated[0]["midpoint_days"], 2),
            "enterprise_completion_acceleration_gain_days": round(
                conservative[-1]["midpoint_days"] - accelerated[-1]["midpoint_days"],
                2,
            ),
        },
        "executive_assessment": "Arquitetura enterprise funcional em aceleração contínua; o gargalo principal é consolidação, sincronização, automação total e hardening enterprise final.",
        "recommended_focus": ACCELERATORS[:4],
        "governance": {
            "deployment": "disabled",
            "production_mutation": "disabled",
            "external_write": "disabled",
            "agent_execution": "disabled",
            "external_ai_call": "disabled",
            "human_review_required": True,
        },
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join([header, separator, body])


def write_reports(projection: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "reqsys-completion-statistical-projection.json").write_text(
        json.dumps(projection, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = projection["statistical_summary"]
    current_rows = [[item["dimension"], f"{item['percent']}%", item["maturity"]] for item in projection["current_state"]]
    completion_rows = [[item["indicator"], f"{item['percent']}%"] for item in projection["completion_indicators"]]
    gap_rows = [[item["area"], f"{item['gap_percent']}%"] for item in projection["remaining_gaps"]]
    velocity_rows = [
        [item["metric"], f"{item['low']}–{item['high']}", item["midpoint"], item["unit"]]
        for item in projection["velocity"]["observed"]
    ]
    conservative_rows = [
        [item["milestone"], f"{item['low_days']}–{item['high_days']} dias", item["midpoint_days"]]
        for item in projection["milestones"]["conservative"]
    ]
    accelerated_rows = [
        [item["milestone"], f"{item['low_days']}–{item['high_days']} dias", item["midpoint_days"]]
        for item in projection["milestones"]["accelerated"]
    ]
    probability_rows = [
        [item["outcome"], f"{item['probability_percent']}%"] for item in projection["final_probabilities"]
    ]
    risk_rows = [[item["type"], item["risk"]] for item in projection["risks"]]
    trend_rows = [[item["indicator"], item["trend"]] for item in projection["trends"]]
    accelerators = "\n".join(f"{index}. {item}" for index, item in enumerate(projection["accelerators"], start=1))
    bottlenecks = "\n".join(f"{index}. {item}" for index, item in enumerate(projection["bottlenecks"], start=1))

    markdown = f"""# ReqSys — Projeção Estatística de Conclusão

## Referência

- Referência temporal: {projection['reference_label']}
- Modo: {projection['mode']}
- Leitura executiva: {projection['executive_assessment']}

## Resumo estatístico

| Métrica | Valor |
|---|---:|
| Maturidade média do ecossistema | {summary['ecosystem_maturity_percent']}% |
| Conclusão real média | {summary['real_completion_percent']}% |
| Gap restante médio | {summary['remaining_gap_percent']}% |
| Gap implementado vs validado | {summary['implemented_to_validated_gap_pp']} pp |
| Padrão ouro total consolidado | {summary['gold_standard_completion_percent']}% |
| Gap para padrão ouro total | {summary['gold_standard_gap_percent']}% |
| Índice estatístico de risco | {summary['risk_score_percent']}% |
| Faixa de risco | {summary['risk_band']} |
| Índice médio de probabilidade final | {summary['probability_index_percent']}% |
| Ganho acelerado em MVP | {summary['mvp_acceleration_gain_days']} dias |
| Ganho acelerado em consolidação enterprise | {summary['enterprise_completion_acceleration_gain_days']} dias |

## Estado atual consolidado

{markdown_table(['Dimensão', 'Status atual', 'Maturidade'], current_rows)}

## Velocidade observada

{markdown_table(['Métrica', 'Faixa', 'Ponto médio', 'Unidade'], velocity_rows)}

## Percentual real de conclusão

{markdown_table(['Indicador', 'Percentual'], completion_rows)}

## Gap restante

{markdown_table(['Área', 'Gap'], gap_rows)}

## Projeção conservadora

{markdown_table(['Marco', 'Estimativa', 'Ponto médio'], conservative_rows)}

## Projeção acelerada recomendada

{markdown_table(['Marco', 'Estimativa', 'Ponto médio'], accelerated_rows)}

## Gargalos principais

{bottlenecks}

## Índice estatístico de risco

{markdown_table(['Tipo', 'Risco'], risk_rows)}

## Tendência atual

{markdown_table(['Indicador', 'Tendência'], trend_rows)}

## Probabilidade estatística final

{markdown_table(['Resultado', 'Probabilidade'], probability_rows)}

## Maior ganho marginal atual

{accelerators}

## Governança

- Deployment: disabled
- Production mutation: disabled
- External write: disabled
- Agent execution: disabled
- External AI call: disabled
- Human review required: true
"""
    (report_dir / "reqsys-completion-statistical-projection.md").write_text(markdown, encoding="utf-8")

    def rows_html(rows: list[list[Any]]) -> str:
        return "".join("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>" for row in rows)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ReqSys Completion Statistical Projection</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1400px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:14px}}
.metric{{font-size:30px;font-weight:bold;margin-top:8px;color:#22c55e}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th,td{{padding:12px;border-bottom:1px solid #1f2937;text-align:left}}
.section{{margin-top:28px}}
.muted{{color:#94a3b8}}
</style>
</head>
<body>
<div class="container">
<h1>ReqSys — Projeção Estatística de Conclusão</h1>
<p class="muted">Referência temporal: {projection['reference_label']} · modo {projection['mode']}</p>
<div class="grid">
<div class="card"><div class="label">Conclusão real média</div><div class="metric">{summary['real_completion_percent']}%</div></div>
<div class="card"><div class="label">Padrão ouro total</div><div class="metric">{summary['gold_standard_completion_percent']}%</div></div>
<div class="card"><div class="label">Gap restante médio</div><div class="metric">{summary['remaining_gap_percent']}%</div></div>
<div class="card"><div class="label">Risco</div><div class="metric">{summary['risk_band']}</div></div>
</div>
<div class="section"><h2>Estado atual consolidado</h2><table><tr><th>Dimensão</th><th>Status</th><th>Maturidade</th></tr>{rows_html(current_rows)}</table></div>
<div class="section"><h2>Percentual real de conclusão</h2><table><tr><th>Indicador</th><th>Percentual</th></tr>{rows_html(completion_rows)}</table></div>
<div class="section"><h2>Projeção acelerada</h2><table><tr><th>Marco</th><th>Estimativa</th><th>Ponto médio</th></tr>{rows_html(accelerated_rows)}</table></div>
<div class="section"><h2>Probabilidade estatística final</h2><table><tr><th>Resultado</th><th>Probabilidade</th></tr>{rows_html(probability_rows)}</table></div>
</div>
</body>
</html>
"""
    (report_dir / "reqsys-completion-statistical-projection.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1]) if len(argv) > 1 else REPORT_DIR
    projection = build_projection()
    write_reports(projection, report_dir)
    print(
        "Completion statistical projection generated: "
        f"{projection['statistical_summary']['real_completion_percent']}% completion"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
