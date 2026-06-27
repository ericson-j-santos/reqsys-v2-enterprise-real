#!/usr/bin/env python3
"""Statistical Completion Projection builder for ReqSys.

Gera o artefato governado ``audit/projection/statistical-completion-projection.json``
e um resumo markdown a partir de dados estatisticos consolidados (report-only).

O artefato e deterministico: nao consome rede, nao depende de segredos e nao
modifica producao. O timestamp ``generated_at`` pode ser passado via variavel de
ambiente ``REQSYS_PROJECTION_GENERATED_AT`` para garantir reprodutibilidade em
testes/CI.
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
DEFAULT_OUTPUT_DIR = Path("audit/projection")
DEFAULT_JSON_FILENAME = "statistical-completion-projection.json"
DEFAULT_MARKDOWN_FILENAME = "statistical-completion-projection.md"


def utc_now_iso() -> str:
    override = os.environ.get("REQSYS_PROJECTION_GENERATED_AT")
    if override:
        return override
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_projection(
    generated_at: str | None = None,
    reference_time: str = DEFAULT_REFERENCE_TIME,
) -> dict[str, Any]:
    """Retorna o payload completo do contrato de projecao estatistica.

    Os valores refletem a leitura executiva atual do projeto, mantida
    sincronizada com ``docs/runbooks/statistical-completion-projection.md``.
    """

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now_iso(),
        "reference_time": reference_time,
        "mode": "report_only",
        "status": "em_consolidacao",
        "headline": (
            "Arquitetura enterprise funcional em aceleracao continua, com "
            "consolidacao, sincronizacao e hardening final pendentes."
        ),
        "executive_summary": (
            "O ReqSys deixou a fase experimental e apresenta governanca, "
            "evolucao incremental consistente, arquitetura viva, analytics "
            "operacional, automacao, observabilidade e fluxo CI/CD maduro. "
            "O que falta concentra-se em consolidacao runtime, sincronizacao "
            "de ambientes, automacao total e hardening enterprise final."
        ),
        "current_state": [
            {"dimension": "Arquitetura base", "status_percent": 88, "maturity": "alta"},
            {"dimension": "CI/CD governado", "status_percent": 82, "maturity": "alta"},
            {"dimension": "Living Architecture", "status_percent": 74, "maturity": "media_alta"},
            {"dimension": "Observabilidade/Analytics", "status_percent": 71, "maturity": "media_alta"},
            {"dimension": "Runtime operacional", "status_percent": 68, "maturity": "media"},
            {"dimension": "UX operacional / dashboards", "status_percent": 72, "maturity": "media_alta"},
            {"dimension": "Automacao autonoma", "status_percent": 63, "maturity": "media"},
            {"dimension": "Governanca enterprise", "status_percent": 79, "maturity": "alta"},
            {"dimension": "Ambientes sincronizados", "status_percent": 61, "maturity": "media"},
            {"dimension": "Padrao ouro consolidado", "status_percent": 54, "maturity": "media"},
        ],
        "velocity": {
            "prs_per_business_day": {"min": 8, "max": 18},
            "green_merges_per_day": {"min": 6, "max": 14},
            "ci_fixes_per_cycle": {"min": 2, "max": 7},
            "safe_parallel_increments": {"min": 3, "max": 5},
            "lead_time_minutes": {"min": 18, "max": 90},
            "ci_stabilization_rate_percent": 83,
            "critical_regression": "baixa",
            "structural_rework": "moderado_baixo",
        },
        "completion_percent": [
            {"indicator": "Codigo implementado", "percent": 78},
            {"indicator": "Codigo validado", "percent": 69},
            {"indicator": "Evidencia operacional consolidada", "percent": 58},
            {"indicator": "Governanca enterprise consolidada", "percent": 64},
            {"indicator": "Ambientes realmente sincronizados", "percent": 61},
            {"indicator": "Runtime navegavel/analitico", "percent": 67},
            {"indicator": "Autonomia operacional", "percent": 55},
            {"indicator": "Padrao ouro total consolidado", "percent": 52},
        ],
        "remaining_gaps_percent": [
            {"area": "Consolidacao runtime", "gap_percent": 18},
            {"area": "Evidencias automatizadas", "gap_percent": 22},
            {"area": "Operacao autonoma", "gap_percent": 31},
            {"area": "Analytics/drill-down total", "gap_percent": 27},
            {"area": "Hardening producao", "gap_percent": 24},
            {"area": "Sincronizacao ambientes", "gap_percent": 39},
            {"area": "Governanca viva completa", "gap_percent": 21},
            {"area": "UX operacional enterprise", "gap_percent": 17},
        ],
        "timelines": {
            "conservative": {
                "assumption": (
                    "Mantendo ritmo atual e sem aceleracao estrutural."
                ),
                "milestones": [
                    {"milestone": "MVP operacional consolidado", "min_days": 3, "max_days": 6},
                    {"milestone": "Ambientes sincronizados", "min_days": 5, "max_days": 9},
                    {"milestone": "Runtime operacional robusto", "min_days": 7, "max_days": 12},
                    {"milestone": "Padrao ouro tecnico", "min_days": 14, "max_days": 22},
                    {"milestone": "Padrao ouro consolidado total", "min_days": 21, "max_days": 35},
                ],
            },
            "accelerated": {
                "assumption": (
                    "Manter incrementos paralelos, CI auto-remediavel e "
                    "validacao continua sob foco Pareto."
                ),
                "preconditions": [
                    "multiplos incrementos paralelos",
                    "ci_auto_remediavel",
                    "branches independentes",
                    "agentes especializados",
                    "validacao continua",
                    "merge incremental governado",
                    "foco_pareto",
                ],
                "milestones": [
                    {"milestone": "MVP robusto", "min_days": 2, "max_days": 4},
                    {"milestone": "Producao utilizavel forte", "min_days": 5, "max_days": 8},
                    {"milestone": "Ambientes quase totalmente sincronizados", "min_days": 4, "max_days": 7},
                    {"milestone": "Padrao ouro tecnico", "min_days": 10, "max_days": 16},
                    {"milestone": "Consolidacao enterprise completa", "min_days": 14, "max_days": 24},
                ],
            },
        },
        "bottlenecks": [
            {"rank": 1, "description": "estabilizacao continua de CI"},
            {"rank": 2, "description": "sincronizacao entre ambientes"},
            {"rank": 3, "description": "evidencia operacional automatica"},
            {"rank": 4, "description": "consolidacao runtime-driven"},
            {"rank": 5, "description": "reducao de acoplamentos residuais"},
            {"rank": 6, "description": "observabilidade fim-a-fim"},
            {"rank": 7, "description": "hardening de producao"},
        ],
        "risks": [
            {"category": "Regressao arquitetural", "level": "baixo"},
            {"category": "Colisao de branches", "level": "medio_baixo"},
            {"category": "Instabilidade CI", "level": "medio"},
            {"category": "Drift entre ambientes", "level": "medio"},
            {"category": "Escalabilidade operacional", "level": "medio"},
            {"category": "Perda de rastreabilidade", "level": "baixo"},
            {"category": "Acoplamento oculto", "level": "medio_baixo"},
        ],
        "trends": [
            {"indicator": "Velocidade", "direction": "up", "intensity": "forte"},
            {"indicator": "Maturidade", "direction": "up", "intensity": "forte"},
            {"indicator": "Governanca", "direction": "up", "intensity": "estavel"},
            {"indicator": "Autonomia", "direction": "up", "intensity": "moderada"},
            {"indicator": "Observabilidade", "direction": "up", "intensity": "forte"},
            {"indicator": "Runtime vivo", "direction": "up", "intensity": "forte"},
            {"indicator": "Producao consolidada", "direction": "up", "intensity": "moderada"},
        ],
        "final_probability_percent": [
            {"outcome": "MVP forte em menos de 1 semana", "probability_percent": 87},
            {"outcome": "Producao utilizavel enterprise", "probability_percent": 81},
            {"outcome": "Padrao ouro tecnico real", "probability_percent": 73},
            {"outcome": "Consolidacao enterprise completa", "probability_percent": 61},
        ],
        "acceleration_levers": [
            {"rank": 1, "lever": "CI auto-healing"},
            {"rank": 2, "lever": "geracao automatica de evidencias"},
            {"rank": 3, "lever": "pipeline de validacao consolidada"},
            {"rank": 4, "lever": "sincronizacao Fly.io/runtime"},
            {"rank": 5, "lever": "monitor operacional centralizado"},
            {"rank": 6, "lever": "contratos/shared packages unicos"},
            {"rank": 7, "lever": "reducao de validacoes manuais"},
        ],
    }

    return payload


def _format_percent_table(rows: list[dict[str, Any]], headers: tuple[str, str]) -> list[str]:
    lines = [f"| {headers[0]} | {headers[1]} |", "|---|---:|"]
    for row in rows:
        key = next(iter(k for k in row.keys() if k != "percent" and k != "gap_percent" and k != "probability_percent"))
        value_key = next(k for k in ("percent", "gap_percent", "probability_percent") if k in row)
        lines.append(f"| {row[key]} | {row[value_key]}% |")
    return lines


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Projecao Estatistica de Conclusao - ReqSys",
        "",
        f"- Schema: `{payload['schema_version']}`",
        f"- Gerado em: `{payload['generated_at']}`",
        f"- Referencia temporal: `{payload['reference_time']}`",
        f"- Modo: `{payload['mode']}`",
        f"- Status: `{payload['status']}`",
        "",
        "## Leitura executiva",
        "",
        payload["executive_summary"],
        "",
        "## Estado atual consolidado",
        "",
        "| Dimensao | Status | Maturidade |",
        "|---|---:|---|",
    ]
    for row in payload["current_state"]:
        lines.append(
            f"| {row['dimension']} | {row['status_percent']}% | {row['maturity']} |"
        )
    velocity = payload["velocity"]
    lines.extend([
        "",
        "## Velocidade atual observada",
        "",
        f"- PRs por dia util: {velocity['prs_per_business_day']['min']}-{velocity['prs_per_business_day']['max']}",
        f"- Merges verdes por dia: {velocity['green_merges_per_day']['min']}-{velocity['green_merges_per_day']['max']}",
        f"- Correcoes CI por ciclo: {velocity['ci_fixes_per_cycle']['min']}-{velocity['ci_fixes_per_cycle']['max']}",
        f"- Incrementos paralelos seguros: {velocity['safe_parallel_increments']['min']}-{velocity['safe_parallel_increments']['max']}",
        f"- Lead time medio PR -> merge: {velocity['lead_time_minutes']['min']}-{velocity['lead_time_minutes']['max']} min",
        f"- Taxa de estabilizacao CI: {velocity['ci_stabilization_rate_percent']}%",
        f"- Regressao critica: {velocity['critical_regression']}",
        f"- Retrabalho estrutural: {velocity['structural_rework']}",
        "",
        "## Percentual real de conclusao",
        "",
    ])
    lines.extend(_format_percent_table(payload["completion_percent"], ("Indicador", "Percentual")))
    lines.extend(["", "## Quanto falta", ""])
    lines.extend(_format_percent_table(payload["remaining_gaps_percent"], ("Area", "Gap")))
    lines.extend([
        "",
        "## Cenario conservador",
        "",
        f"_Premissa:_ {payload['timelines']['conservative']['assumption']}",
        "",
        "| Marco | Estimativa (dias) |",
        "|---|---:|",
    ])
    for milestone in payload["timelines"]["conservative"]["milestones"]:
        lines.append(
            f"| {milestone['milestone']} | {milestone['min_days']}-{milestone['max_days']} |"
        )
    accelerated = payload["timelines"]["accelerated"]
    lines.extend([
        "",
        "## Cenario acelerado (recomendado)",
        "",
        f"_Premissa:_ {accelerated['assumption']}",
        "",
        "Pre-condicoes:",
    ])
    lines.extend([f"- {item}" for item in accelerated["preconditions"]])
    lines.extend(["", "| Marco | Estimativa (dias) |", "|---|---:|"])
    for milestone in accelerated["milestones"]:
        lines.append(
            f"| {milestone['milestone']} | {milestone['min_days']}-{milestone['max_days']} |"
        )
    lines.extend(["", "## Gargalos principais", ""])
    lines.extend([f"{item['rank']}. {item['description']}" for item in payload["bottlenecks"]])
    lines.extend(["", "## Indice estatistico de risco", "", "| Categoria | Nivel |", "|---|---|"])
    for row in payload["risks"]:
        lines.append(f"| {row['category']} | {row['level']} |")
    lines.extend([
        "",
        "## Tendencia atual",
        "",
        "| Indicador | Direcao | Intensidade |",
        "|---|---|---|",
    ])
    for row in payload["trends"]:
        lines.append(f"| {row['indicator']} | {row['direction']} | {row['intensity']} |")
    lines.extend(["", "## Estimativa realista final", ""])
    lines.extend(_format_percent_table(payload["final_probability_percent"], ("Resultado", "Probabilidade")))
    lines.extend(["", "## O que mais acelera agora", ""])
    lines.extend([f"{item['rank']}. {item['lever']}" for item in payload["acceleration_levers"]])
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    payload: dict[str, Any],
    output_dir: Path,
    json_filename: str = DEFAULT_JSON_FILENAME,
    markdown_filename: str = DEFAULT_MARKDOWN_FILENAME,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / json_filename
    markdown_path = output_dir / markdown_filename
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Diretorio onde gravar os artefatos (default: audit/projection).",
    )
    parser.add_argument(
        "--reference-time",
        default=DEFAULT_REFERENCE_TIME,
        help="Marca temporal de referencia exibida no artefato.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Imprime o JSON no stdout alem de gravar em disco.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_projection(reference_time=args.reference_time)
    json_path, markdown_path = write_outputs(payload, args.output_dir)
    print(f"[projection] JSON: {json_path}")
    print(f"[projection] Markdown: {markdown_path}")
    if args.print:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
