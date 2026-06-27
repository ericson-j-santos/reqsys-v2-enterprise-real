#!/usr/bin/env python3
"""Completion Projection Report (Projecao Estatistica de Conclusao) for ReqSys.

Report-only generator that consolidates the statistical completion projection of
the ReqSys ecosystem into a governed JSON/Markdown artifact. The artifact feeds
the operational command center dashboard and keeps the projection traceable.

The numbers reflect the latest executive projection snapshot. Derived metrics
(overall completion, average maturity, average gap and status) are computed from
the source tables so the artifact stays internally consistent and testable.

This is strictly report-only: it never blocks merges and never substitutes the
mandatory CI gates. It documents target/projected state, not evidenced state.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

SCHEMA_VERSION = "1.0.0"
REFERENCE_TIME = "2026-06-27T21:00:00-03:00"

CURRENT_STATE: list[dict[str, Any]] = [
    {"dimension": "arquitetura_base", "status_percent": 88, "maturity": "alta"},
    {"dimension": "ci_cd_governado", "status_percent": 82, "maturity": "alta"},
    {"dimension": "living_architecture", "status_percent": 74, "maturity": "media_alta"},
    {"dimension": "observabilidade_analytics", "status_percent": 71, "maturity": "media_alta"},
    {"dimension": "runtime_operacional", "status_percent": 68, "maturity": "media"},
    {"dimension": "ux_operacional_dashboards", "status_percent": 72, "maturity": "media_alta"},
    {"dimension": "automacao_autonoma", "status_percent": 63, "maturity": "media"},
    {"dimension": "governanca_enterprise", "status_percent": 79, "maturity": "alta"},
    {"dimension": "ambientes_sincronizados", "status_percent": 61, "maturity": "media"},
    {"dimension": "producao_padrao_ouro", "status_percent": 54, "maturity": "media"},
]

VELOCITY: dict[str, Any] = {
    "prs_per_business_day_min": 8,
    "prs_per_business_day_max": 18,
    "green_merges_per_day_min": 6,
    "green_merges_per_day_max": 14,
    "ci_fixes_per_cycle_min": 2,
    "ci_fixes_per_cycle_max": 7,
    "safe_parallel_increments_min": 3,
    "safe_parallel_increments_max": 5,
    "lead_time_pr_to_merge_min_minutes": 18,
    "lead_time_pr_to_merge_max_minutes": 90,
    "ci_stabilization_rate_percent": 83,
    "critical_regression_level": "baixa",
    "structural_rework_level": "moderado_baixo",
}

COMPLETION: list[dict[str, Any]] = [
    {"indicator": "codigo_implementado", "percent": 78},
    {"indicator": "codigo_validado", "percent": 69},
    {"indicator": "evidencia_operacional_consolidada", "percent": 58},
    {"indicator": "governanca_enterprise_consolidada", "percent": 64},
    {"indicator": "ambientes_realmente_sincronizados", "percent": 61},
    {"indicator": "runtime_navegavel_analitico", "percent": 67},
    {"indicator": "autonomia_operacional", "percent": 55},
    {"indicator": "padrao_ouro_total_consolidado", "percent": 52},
]

GAPS: list[dict[str, Any]] = [
    {"area": "consolidacao_runtime", "gap_percent": 18},
    {"area": "evidencias_automatizadas", "gap_percent": 22},
    {"area": "operacao_autonoma", "gap_percent": 31},
    {"area": "analytics_drilldown_total", "gap_percent": 27},
    {"area": "hardening_producao", "gap_percent": 24},
    {"area": "sincronizacao_ambientes", "gap_percent": 39},
    {"area": "governanca_viva_completa", "gap_percent": 21},
    {"area": "ux_operacional_enterprise", "gap_percent": 17},
]

TIME_PROJECTION_CONSERVATIVE: list[dict[str, Any]] = [
    {"milestone": "mvp_operacional_consolidado", "min_days": 3, "max_days": 6},
    {"milestone": "ambientes_sincronizados", "min_days": 5, "max_days": 9},
    {"milestone": "runtime_operacional_robusto", "min_days": 7, "max_days": 12},
    {"milestone": "padrao_ouro_tecnico", "min_days": 14, "max_days": 22},
    {"milestone": "padrao_ouro_consolidado_total", "min_days": 21, "max_days": 35},
]

TIME_PROJECTION_ACCELERATED: list[dict[str, Any]] = [
    {"milestone": "mvp_robusto", "min_days": 2, "max_days": 4},
    {"milestone": "producao_utilizavel_forte", "min_days": 5, "max_days": 8},
    {"milestone": "ambientes_quase_totalmente_sincronizados", "min_days": 4, "max_days": 7},
    {"milestone": "padrao_ouro_tecnico", "min_days": 10, "max_days": 16},
    {"milestone": "consolidacao_enterprise_completa", "min_days": 14, "max_days": 24},
]

BOTTLENECKS: list[str] = [
    "estabilizacao_continua_de_ci",
    "sincronizacao_entre_ambientes",
    "evidencia_operacional_automatica",
    "consolidacao_runtime_driven",
    "reducao_de_acoplamentos_residuais",
    "observabilidade_fim_a_fim",
    "hardening_de_producao",
]

RISK_INDEX: list[dict[str, str]] = [
    {"type": "regressao_arquitetural", "level": "baixo"},
    {"type": "colisao_de_branches", "level": "medio_baixo"},
    {"type": "instabilidade_ci", "level": "medio"},
    {"type": "drift_entre_ambientes", "level": "medio"},
    {"type": "escalabilidade_operacional", "level": "medio"},
    {"type": "perda_de_rastreabilidade", "level": "baixo"},
    {"type": "acoplamento_oculto", "level": "medio_baixo"},
]

TREND: list[dict[str, str]] = [
    {"indicator": "velocidade", "direction": "up", "strength": "forte"},
    {"indicator": "maturidade", "direction": "up", "strength": "forte"},
    {"indicator": "governanca", "direction": "up", "strength": "estavel"},
    {"indicator": "autonomia", "direction": "up", "strength": "moderada"},
    {"indicator": "observabilidade", "direction": "up", "strength": "forte"},
    {"indicator": "runtime_vivo", "direction": "up", "strength": "forte"},
    {"indicator": "producao_consolidada", "direction": "up", "strength": "moderada"},
]

PROBABILITIES: list[dict[str, Any]] = [
    {"outcome": "mvp_forte_em_menos_de_1_semana", "probability_percent": 87},
    {"outcome": "producao_utilizavel_enterprise", "probability_percent": 81},
    {"outcome": "padrao_ouro_tecnico_real", "probability_percent": 73},
    {"outcome": "consolidacao_enterprise_completa", "probability_percent": 61},
]

ACCELERATORS: list[str] = [
    "ci_auto_healing",
    "geracao_automatica_de_evidencias",
    "pipeline_de_validacao_consolidada",
    "sincronizacao_fly_io_runtime",
    "monitor_operacional_centralizado",
    "contratos_shared_packages_unicos",
    "reducao_de_validacoes_manuais",
]

EXECUTIVE_READING = (
    "Arquitetura enterprise funcional em aceleracao continua; o que falta e "
    "principalmente consolidacao, sincronizacao, automacao total e hardening "
    "enterprise final."
)


def _round1(value: float) -> float:
    return round(value, 1)


def _derive_status(overall_completion: float, probabilities: list[dict[str, Any]]) -> str:
    """Derive a coarse projection status from completion and probabilities."""
    mvp_prob = next(
        (item["probability_percent"] for item in probabilities if item["outcome"].startswith("mvp")),
        0,
    )
    if overall_completion >= 80:
        return "consolidado"
    if overall_completion >= 60 and mvp_prob >= 80:
        return "em_aceleracao"
    if overall_completion >= 50:
        return "em_consolidacao"
    return "em_evolucao"


def build_report(
    repository: str = "",
    run_id: str = "",
    event_name: str = "local",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the completion projection report payload with derived metrics."""
    overall_completion = _round1(mean(item["percent"] for item in COMPLETION))
    average_maturity = _round1(mean(item["status_percent"] for item in CURRENT_STATE))
    average_gap = _round1(mean(item["gap_percent"] for item in GAPS))
    remaining_to_gold = _round1(100 - COMPLETION[-1]["percent"])

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repository,
        "run_id": run_id,
        "event_name": event_name,
        "reference_time": REFERENCE_TIME,
        "overall_completion_percent": overall_completion,
        "average_maturity_percent": average_maturity,
        "average_gap_pp": average_gap,
        "remaining_to_gold_pp": remaining_to_gold,
        "status": _derive_status(overall_completion, PROBABILITIES),
        "current_state": CURRENT_STATE,
        "velocity": VELOCITY,
        "completion": COMPLETION,
        "gaps": GAPS,
        "time_projection_conservative": TIME_PROJECTION_CONSERVATIVE,
        "time_projection_accelerated": TIME_PROJECTION_ACCELERATED,
        "bottlenecks": BOTTLENECKS,
        "risk_index": RISK_INDEX,
        "trend": TREND,
        "probabilities": PROBABILITIES,
        "accelerators": ACCELERATORS,
        "executive_reading": EXECUTIVE_READING,
        "mode": "report_only",
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render a human-readable Markdown summary of the projection."""
    lines = [
        "# Completion Projection Report — ReqSys",
        "",
        f"- Gerado em (UTC): `{report['generated_at']}`",
        f"- Referencia temporal: `{report['reference_time']}`",
        f"- Status da projecao: `{report['status']}`",
        f"- Conclusao geral: `{report['overall_completion_percent']}%`",
        f"- Maturidade media: `{report['average_maturity_percent']}%`",
        f"- Gap medio: `{report['average_gap_pp']} p.p.`",
        f"- Restante para padrao ouro: `{report['remaining_to_gold_pp']} p.p.`",
        "- Modo: `report_only`",
        "",
        "## Conclusao por indicador",
        "",
        "| Indicador | % |",
        "|---|---:|",
    ]
    lines.extend(f"| {item['indicator']} | {item['percent']}% |" for item in report["completion"])
    lines.extend(
        [
            "",
            "## Gaps restantes",
            "",
            "| Area | Gap |",
            "|---|---:|",
        ]
    )
    lines.extend(f"| {item['area']} | {item['gap_percent']}% |" for item in report["gaps"])
    lines.extend(
        [
            "",
            "## Probabilidades",
            "",
            "| Resultado | Probabilidade |",
            "|---|---:|",
        ]
    )
    lines.extend(
        f"| {item['outcome']} | {item['probability_percent']}% |" for item in report["probabilities"]
    )
    lines.extend(["", "## Leitura executiva", "", report["executive_reading"], ""])
    return "\n".join(lines) + "\n"


def write_artifacts(report: dict[str, Any], output_dir: Path) -> None:
    """Persist the JSON and Markdown artifacts to ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "completion-projection-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "completion-projection-report.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the ReqSys completion projection report (report-only)."
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", "local"))
    parser.add_argument("--output-dir", default="audit/projection")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(
        repository=args.repo,
        run_id=args.run_id,
        event_name=args.event_name,
    )
    write_artifacts(report, Path(args.output_dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
