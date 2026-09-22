#!/usr/bin/env python3
"""Endurece as decisões do inventário de GitHub Actions.

A ausência de um workflow nas últimas N execuções não é evidência suficiente
para remoção. Este gate rebaixa recomendações destrutivas de baixa confiança
para uma decisão conservadora antes da publicação do artifact.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


CONSOLIDATED_OPERATOR = ".github/workflows/actions-auto-operator.yml"


def normalize_decision(workflow: dict[str, Any]) -> dict[str, Any]:
    recommendation = workflow.get("recommendation")
    confidence = workflow.get("confidence")
    triggers = set(workflow.get("triggers") or [])
    path = workflow.get("path") or ""

    if path == CONSOLIDATED_OPERATOR:
        workflow["recommendation"] = "MANTER"
        workflow["confidence"] = "alta"
        workflow["requires_human_validation"] = False
        workflow["rationale"] = [
            "operador consolidado canônico de retentativas governadas",
            "substitui o workflow auto-rerun-governed removido nesta mudança",
        ]
        return workflow

    if recommendation != "REMOVER" or confidence != "baixa":
        return workflow

    rationale = list(workflow.get("rationale") or [])
    rationale.append("ausência na amostra de execuções não comprova desuso")

    if triggers and triggers <= {"workflow_dispatch"}:
        workflow["recommendation"] = "TRANSFORMAR_EM_REUTILIZAVEL"
        rationale.append("workflow exclusivamente manual deve ser consolidado/reutilizado antes de eventual remoção")
    elif "workflow_run" in triggers:
        workflow["recommendation"] = "FUNDIR"
        rationale.append("workflow em cascata deve ser analisado junto ao workflow de origem")
    else:
        workflow["recommendation"] = "MANTER"
        rationale.append("gatilho automático ou periódico exige evidência adicional antes de qualquer remoção")

    workflow["confidence"] = "baixa"
    workflow["requires_human_validation"] = True
    workflow["rationale"] = rationale
    return workflow


def rebuild_summary(payload: dict[str, Any]) -> None:
    workflows = payload.get("workflows") or []
    payload["summary"]["recommendations"] = dict(Counter(item["recommendation"] for item in workflows))
    payload["metadata"]["decision_gate_version"] = "1.0.0"
    payload["metadata"]["sample_absence_is_removal_evidence"] = False


def write_outputs(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    workflows = payload.get("workflows") or []
    (output_dir / "workflows.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if workflows:
        fields = list(workflows[0].keys())
        with (output_dir / "workflows.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for item in workflows:
                row = dict(item)
                for key, value in list(row.items()):
                    if isinstance(value, list):
                        row[key] = " | ".join(str(part) for part in value)
                writer.writerow(row)

    summary = payload["summary"]
    lines = [
        "# Auditoria validada dos GitHub Actions",
        "",
        f"Workflows analisados: **{summary['total_workflows']}**",
        f"Execuções amostradas: **{payload['metadata'].get('sampled_runs', 0)}**",
        "",
        "## Recomendações após gate conservador",
        "",
        "| Recomendação | Quantidade |",
        "|---|---:|",
    ]
    for key in ("MANTER", "FUNDIR", "TRANSFORMAR_EM_REUTILIZAVEL", "REMOVER"):
        lines.append(f"| {key} | {summary['recommendations'].get(key, 0)} |")
    lines.extend([
        "",
        "## Regra de segurança",
        "",
        "A ausência nas últimas execuções amostradas nunca é usada isoladamente para recomendar remoção.",
        "",
        "## Inventário",
        "",
        "| Workflow | Gatilhos | Dependentes | Último uso observado | Recomendação | Confiança |",
        "|---|---|---:|---|---|---|",
    ])
    for item in workflows:
        lines.append(
            f"| `{item['path']}` | {', '.join(item.get('triggers') or []) or '-'} | "
            f"{len(item.get('callers') or [])} | {item.get('last_use_observed_at') or 'não observado'} | "
            f"{item['recommendation']} | {item['confidence']} |"
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aplica gate conservador ao inventário de workflows.")
    parser.add_argument("--input", default="artifacts/workflow-inventory-audit/workflows.json")
    parser.add_argument("--output-dir", default="artifacts/workflow-inventory-audit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = Path(args.input)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["workflows"] = [normalize_decision(dict(item)) for item in payload.get("workflows") or []]
    rebuild_summary(payload)
    write_outputs(payload, Path(args.output_dir))
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
