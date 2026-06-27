#!/usr/bin/env python3
"""Gera o Completion Projection Report (Projecao Estatistica de Conclusao) do ReqSys.

Entrada: dados consolidados da projecao estatistica (estado atual, velocidade,
percentuais de conclusao, gaps, projecoes de marcos, risco e probabilidades).
Saida: artifact JSON + resumo Markdown consumido pelo dashboard dinamico.

Este script e deterministico, report-only e nao acessa rede nem segredos.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
DEFAULT_REFERENCE_TIME = "2026-06-27T21:00:00-03:00"

CURRENT_STATE = [
    {"dimension": "arquitetura_base", "status_percent": 88, "maturity": "alta"},
    {"dimension": "cicd_governado", "status_percent": 82, "maturity": "alta"},
    {"dimension": "living_architecture", "status_percent": 74, "maturity": "media_alta"},
    {"dimension": "observabilidade_analytics", "status_percent": 71, "maturity": "media_alta"},
    {"dimension": "runtime_operacional", "status_percent": 68, "maturity": "media"},
    {"dimension": "ux_operacional_dashboards", "status_percent": 72, "maturity": "media_alta"},
    {"dimension": "automacao_autonoma", "status_percent": 63, "maturity": "media"},
    {"dimension": "governanca_enterprise", "status_percent": 79, "maturity": "alta"},
    {"dimension": "ambientes_sincronizados", "status_percent": 61, "maturity": "media"},
    {"dimension": "producao_padrao_ouro", "status_percent": 54, "maturity": "media"},
]

COMPLETION_INDICATORS = [
    {"indicator": "codigo_implementado", "percent": 78},
    {"indicator": "codigo_validado", "percent": 69},
    {"indicator": "evidencia_operacional_consolidada", "percent": 58},
    {"indicator": "governanca_enterprise_consolidada", "percent": 64},
    {"indicator": "ambientes_realmente_sincronizados", "percent": 61},
    {"indicator": "runtime_navegavel_analitico", "percent": 67},
    {"indicator": "autonomia_operacional", "percent": 55},
    {"indicator": "padrao_ouro_total_consolidado", "percent": 52},
]

REMAINING_GAPS = [
    {"area": "consolidacao_runtime", "gap_pp": 18},
    {"area": "evidencias_automatizadas", "gap_pp": 22},
    {"area": "operacao_autonoma", "gap_pp": 31},
    {"area": "analytics_drilldown_total", "gap_pp": 27},
    {"area": "hardening_producao", "gap_pp": 24},
    {"area": "sincronizacao_ambientes", "gap_pp": 39},
    {"area": "governanca_viva_completa", "gap_pp": 21},
    {"area": "ux_operacional_enterprise", "gap_pp": 17},
]

VELOCITY = {
    "prs_per_business_day_min": 8,
    "prs_per_business_day_max": 18,
    "green_merges_per_day_min": 6,
    "green_merges_per_day_max": 14,
    "ci_fixes_per_cycle_min": 2,
    "ci_fixes_per_cycle_max": 7,
    "safe_parallel_increments_min": 3,
    "safe_parallel_increments_max": 5,
    "lead_time_min_minutes": 18,
    "lead_time_max_minutes": 90,
    "ci_stabilization_rate_percent": 83,
    "critical_regression": "low",
    "structural_rework": "moderate_low",
}

PROJECTION_CONSERVATIVE = [
    {"milestone": "mvp_operacional_consolidado", "estimate_label": "3-6 dias", "days_min": 3, "days_max": 6},
    {"milestone": "ambientes_sincronizados", "estimate_label": "5-9 dias", "days_min": 5, "days_max": 9},
    {"milestone": "runtime_operacional_robusto", "estimate_label": "7-12 dias", "days_min": 7, "days_max": 12},
    {"milestone": "padrao_ouro_tecnico", "estimate_label": "14-22 dias", "days_min": 14, "days_max": 22},
    {"milestone": "padrao_ouro_consolidado_total", "estimate_label": "21-35 dias", "days_min": 21, "days_max": 35},
]

PROJECTION_ACCELERATED = [
    {"milestone": "mvp_robusto", "estimate_label": "2-4 dias", "days_min": 2, "days_max": 4},
    {"milestone": "producao_utilizavel_forte", "estimate_label": "5-8 dias", "days_min": 5, "days_max": 8},
    {"milestone": "ambientes_quase_totalmente_sincronizados", "estimate_label": "4-7 dias", "days_min": 4, "days_max": 7},
    {"milestone": "padrao_ouro_tecnico", "estimate_label": "10-16 dias", "days_min": 10, "days_max": 16},
    {"milestone": "consolidacao_enterprise_completa", "estimate_label": "14-24 dias", "days_min": 14, "days_max": 24},
]

PRIMARY_BOTTLENECKS = [
    "estabilizacao_continua_ci",
    "sincronizacao_entre_ambientes",
    "evidencia_operacional_automatica",
    "consolidacao_runtime_driven",
    "reducao_de_acoplamentos_residuais",
    "observabilidade_fim_a_fim",
    "hardening_de_producao",
]

RISK_INDEX = [
    {"type": "regressao_arquitetural", "level": "low"},
    {"type": "colisao_de_branches", "level": "medium_low"},
    {"type": "instabilidade_ci", "level": "medium"},
    {"type": "drift_entre_ambientes", "level": "medium"},
    {"type": "escalabilidade_operacional", "level": "medium"},
    {"type": "perda_de_rastreabilidade", "level": "low"},
    {"type": "acoplamento_oculto", "level": "medium_low"},
]

TRENDS = [
    {"indicator": "velocidade", "trend": "up_strong"},
    {"indicator": "maturidade", "trend": "up_strong"},
    {"indicator": "governanca", "trend": "up_stable"},
    {"indicator": "autonomia", "trend": "up_moderate"},
    {"indicator": "observabilidade", "trend": "up_strong"},
    {"indicator": "runtime_vivo", "trend": "up_strong"},
    {"indicator": "producao_consolidada", "trend": "up_moderate"},
]

PROBABILITIES = [
    {"outcome": "mvp_forte_menos_de_1_semana", "probability_percent": 87},
    {"outcome": "producao_utilizavel_enterprise", "probability_percent": 81},
    {"outcome": "padrao_ouro_tecnico_real", "probability_percent": 73},
    {"outcome": "consolidacao_enterprise_completa", "probability_percent": 61},
]

ACCELERATION_LEVERS = [
    "ci_auto_healing",
    "geracao_automatica_de_evidencias",
    "pipeline_de_validacao_consolidada",
    "sincronizacao_flyio_runtime",
    "monitor_operacional_centralizado",
    "contratos_shared_packages_unicos",
    "reducao_de_validacoes_manuais",
]

EXECUTIVE_READING = {
    "headline": "Arquitetura enterprise funcional em aceleracao continua",
    "phase": "nao_experimental",
    "demonstrated": [
        "governanca",
        "evolucao_incremental_consistente",
        "arquitetura_viva",
        "analytics_operacional",
        "automacao",
        "observabilidade",
        "fluxo_cicd_maduro",
        "continuidade_operacional",
    ],
    "remaining_focus": [
        "consolidacao",
        "sincronizacao",
        "automacao_total",
        "hardening_enterprise_final",
    ],
}


def _round1(value: float) -> float:
    return round(value * 10) / 10


def _average(values: list[float]) -> float:
    return _round1(sum(values) / len(values)) if values else 0.0


def _status_from_completion(percent: float) -> str:
    if percent >= 85:
        return "consolidado"
    if percent >= 55:
        return "em_consolidacao"
    return "em_evolucao"


def build_completion_projection(
    repository: str,
    run_id: str,
    event_name: str,
    generated_at: str | None = None,
    reference_time: str = DEFAULT_REFERENCE_TIME,
) -> dict[str, Any]:
    """Constroi o payload deterministico do Completion Projection Report."""
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    overall_completion = _average([item["percent"] for item in COMPLETION_INDICATORS])
    overall_maturity = _average([item["status_percent"] for item in CURRENT_STATE])
    average_gap = _average([item["gap_pp"] for item in REMAINING_GAPS])
    probability_index = {item["outcome"]: item["probability_percent"] for item in PROBABILITIES}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "repository": repository or "unknown",
        "run_id": str(run_id or "local"),
        "event_name": event_name or "local",
        "reference_time": reference_time,
        "overall_completion_percent": overall_completion,
        "overall_maturity_percent": overall_maturity,
        "average_gap_pp": average_gap,
        "status": _status_from_completion(overall_completion),
        "mvp_probability_percent": probability_index["mvp_forte_menos_de_1_semana"],
        "enterprise_consolidation_probability_percent": probability_index["consolidacao_enterprise_completa"],
        "current_state": CURRENT_STATE,
        "velocity": VELOCITY,
        "completion_indicators": COMPLETION_INDICATORS,
        "remaining_gaps": REMAINING_GAPS,
        "projection_conservative": PROJECTION_CONSERVATIVE,
        "projection_accelerated": PROJECTION_ACCELERATED,
        "primary_bottlenecks": PRIMARY_BOTTLENECKS,
        "risk_index": RISK_INDEX,
        "trends": TRENDS,
        "probabilities": PROBABILITIES,
        "acceleration_levers": ACCELERATION_LEVERS,
        "executive_reading": EXECUTIVE_READING,
        "mode": "report_only",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Completion Projection Report — ReqSys",
        "",
        f"- Referencia temporal: {report['reference_time']}",
        f"- Conclusao geral: {report['overall_completion_percent']}%",
        f"- Maturidade media: {report['overall_maturity_percent']}%",
        f"- Gap medio: {report['average_gap_pp']} p.p.",
        f"- Status: {report['status']}",
        f"- Probabilidade MVP forte (<1 semana): {report['mvp_probability_percent']}%",
        f"- Probabilidade consolidacao enterprise: {report['enterprise_consolidation_probability_percent']}%",
        "",
        "## Indicadores de conclusao",
        "",
        "| Indicador | % |",
        "|---|---:|",
    ]
    lines.extend(f"| {item['indicator']} | {item['percent']} |" for item in report["completion_indicators"])
    lines += ["", "## Projecao conservadora", "", "| Marco | Estimativa |", "|---|---|"]
    lines.extend(f"| {item['milestone']} | {item['estimate_label']} |" for item in report["projection_conservative"])
    lines += ["", "## Projecao acelerada", "", "| Marco | Estimativa |", "|---|---|"]
    lines.extend(f"| {item['milestone']} | {item['estimate_label']} |" for item in report["projection_accelerated"])
    lines += ["", "## Principais gargalos", ""]
    lines.extend(f"- {item}" for item in report["primary_bottlenecks"])
    lines += [
        "",
        "## Regras",
        "",
        "- Artifact report-only: apoio operacional, nao substitui CI obrigatorio.",
        "- Estado alvo/projetado nao deve ser confundido com estado evidenciado.",
        "- Estimativas sao projecoes estatisticas baseadas em ritmo observado.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o Completion Projection Report do ReqSys")
    parser.add_argument("--repository", default=os.environ.get("REPOSITORY", "unknown"))
    parser.add_argument("--run-id", default=os.environ.get("RUN_ID", "local"))
    parser.add_argument("--event-name", default=os.environ.get("EVENT_NAME", "local"))
    parser.add_argument("--reference-time", default=DEFAULT_REFERENCE_TIME)
    parser.add_argument("--output-dir", default="audit/projection")
    args = parser.parse_args()

    report = build_completion_projection(
        repository=args.repository,
        run_id=args.run_id,
        event_name=args.event_name,
        reference_time=args.reference_time,
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "completion-projection-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "completion-projection-report.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
