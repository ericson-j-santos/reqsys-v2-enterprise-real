#!/usr/bin/env python3
"""Classify CI logs and operational text using a versioned failure pattern catalog.

The engine is deterministic, dependency-free and does not execute remediation.
It reads one or more text files, matches known patterns and emits JSON/Markdown evidence.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Match:
    pattern_id: str
    name: str
    category: str
    severity: str
    confidence: str
    matched_text: str
    source_file: str
    recommended_action: str
    can_auto_rerun: bool
    can_auto_fix: bool
    tags: list[str]


def load_catalog(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        catalog = json.load(file)

    if not isinstance(catalog, dict):
        raise ValueError("Catalogo invalido: esperado objeto JSON.")

    patterns = catalog.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        raise ValueError("Catalogo invalido: campo 'patterns' deve ser uma lista nao vazia.")

    return catalog


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def normalize(text: str) -> str:
    return text.lower()


def find_matches(catalog: dict[str, Any], files: list[Path]) -> list[Match]:
    matches: list[Match] = []

    for file_path in files:
        content = read_text(file_path)
        normalized_content = normalize(content)

        for pattern in catalog["patterns"]:
            for token in pattern.get("match_any", []):
                token_text = str(token)
                if normalize(token_text) in normalized_content:
                    matches.append(
                        Match(
                            pattern_id=str(pattern["id"]),
                            name=str(pattern["name"]),
                            category=str(pattern["category"]),
                            severity=str(pattern["severity"]),
                            confidence=str(pattern.get("confidence", "medium")),
                            matched_text=token_text,
                            source_file=str(file_path),
                            recommended_action=str(pattern["recommended_action"]),
                            can_auto_rerun=bool(pattern.get("can_auto_rerun", False)),
                            can_auto_fix=bool(pattern.get("can_auto_fix", False)),
                            tags=[str(tag) for tag in pattern.get("tags", [])],
                        )
                    )
                    break

    return deduplicate_matches(matches)


def deduplicate_matches(matches: list[Match]) -> list[Match]:
    seen: set[tuple[str, str]] = set()
    deduped: list[Match] = []
    for match in matches:
        key = (match.pattern_id, match.source_file)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(match)
    return deduped


def severity_score(severity: str) -> int:
    return {
        "critical": 100,
        "high": 80,
        "medium": 50,
        "low": 20,
        "info": 5,
    }.get(severity.lower(), 30)


def calculate_risk(matches: list[Match]) -> dict[str, Any]:
    if not matches:
        return {
            "score": 0,
            "status": "VERDE",
            "description": "Nenhum padrao conhecido de falha foi identificado.",
        }

    raw_score = sum(severity_score(match.severity) for match in matches)
    score = min(100, raw_score)

    if score >= 80:
        status = "VERMELHO"
        description = "Foram identificadas falhas conhecidas de alta severidade. Priorizar estabilizacao antes de prosseguir."
    elif score >= 40:
        status = "AMARELO"
        description = "Foram identificados sinais relevantes. Exige revisao antes de automacao ou merge."
    else:
        status = "VERDE"
        description = "Foram identificados apenas sinais de baixo risco operacional."

    return {
        "score": score,
        "status": status,
        "description": description,
    }


def build_report(catalog: dict[str, Any], files: list[Path]) -> dict[str, Any]:
    matches = find_matches(catalog, files)
    risk = calculate_risk(matches)
    categories = Counter(match.category for match in matches)
    severities = Counter(match.severity for match in matches)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_schema_version": catalog.get("schema_version"),
        "files_analyzed": [str(path) for path in files],
        "summary": {
            "matches": len(matches),
            "categories": dict(categories),
            "severities": dict(severities),
            "risk": risk,
        },
        "matches": [match.__dict__ for match in matches],
        "safety_policy": catalog.get("safety_policy", {}),
        "limits": [
            "Classificacao baseada em padroes deterministos e texto disponivel.",
            "Nao executa rerun, merge, push, deploy ou remediacao automatica.",
            "Resultado sem matches nao garante ausencia de falha desconhecida.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    risk = report["summary"]["risk"]
    lines = [
        "# Failure Pattern Engine — Relatorio",
        "",
        f"Atualizado em UTC: `{report['generated_at_utc']}`",
        "",
        "## Semaforo",
        "",
        f"**Status:** {risk['status']}",
        f"**Score de risco:** {risk['score']}%",
        f"**Leitura:** {risk['description']}",
        "",
        "## Escopo analisado",
        "",
    ]

    for file_name in report["files_analyzed"]:
        lines.append(f"- `{file_name}`")

    lines.extend([
        "",
        "## Estatisticas",
        "",
        "| Indicador | Valor |",
        "|---|---:|",
        f"| Matches | {report['summary']['matches']} |",
        f"| Categorias | {len(report['summary']['categories'])} |",
        f"| Severidades | {len(report['summary']['severities'])} |",
        "",
        "## Matches encontrados",
        "",
    ])

    matches = report.get("matches", [])
    if not matches:
        lines.append("Nenhum padrao conhecido identificado.")
    else:
        lines.extend([
            "| ID | Severidade | Categoria | Arquivo | Acao recomendada |",
            "|---|---|---|---|---|",
        ])
        for match in matches:
            action = str(match["recommended_action"]).replace("|", "-")
            lines.append(
                f"| {match['pattern_id']} | {match['severity']} | {match['category']} | `{match['source_file']}` | {action} |"
            )

    lines.extend([
        "",
        "## Limites operacionais",
        "",
    ])
    lines.extend(f"- {item}" for item in report["limits"])
    lines.append("")

    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "failure-pattern-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "failure-pattern-report.md").write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify known operational failure patterns.")
    parser.add_argument("--catalog", type=Path, default=Path("config/failure-patterns.json"))
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/failure-pattern-engine"))
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    report = build_report(catalog, args.input)
    write_outputs(report, args.out_dir)
    print(render_markdown(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
