#!/usr/bin/env python3
"""Valida a estrutura do relatório anual de segurança cibernética (BACEN-08).

Não valida conteúdo de negócio (isso exige revisão humana). Garante apenas que:
- o relatório existe e os blocos gerados automaticamente foram preenchidos
  (i.e. o gerador já rodou pelo menos uma vez sobre a versão atual da matriz);
- o registro de designação executiva existe e tem um status reconhecido;
- lacunas que ainda dependem de decisão humana (designação executiva, seções
  narrativas) são reportadas como avisos, nunca como declaração de conformidade;
- nenhum escalar agregado de cobertura regulatória é publicado enquanto o eixo
  normativo vigente não estiver integralmente modelado e avaliado.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.generate_bacen_annual_report import parse_designation  # noqa: E402

VALID_DESIGNATION_STATUS = {"pending_formal_designation", "designated", "expired"}
NARRATIVE_PLACEHOLDER_PATTERN = re.compile(r"\*\(seção narrativa")
GENERATOR_PLACEHOLDER = "(executar o gerador para preencher)"
PROHIBITED_COVERAGE_SCALAR_PATTERNS = (
    re.compile(r"Cobertura\s+ponderada\s*:\s*\*\*?\s*\d+(?:[.,]\d+)?%", re.IGNORECASE),
    re.compile(r"Cobertura\s+regulat[óo]ria\s*:\s*\*\*?\s*\d+(?:[.,]\d+)?%", re.IGNORECASE),
)


def validate(report_text: str, designation_text: str) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []

    if "<!-- BACEN-08:EXECUTIVE:START -->" not in report_text:
        errors.append("bloco EXECUTIVE ausente no relatório")
    if "<!-- BACEN-08:CONTROLS-SUMMARY:START -->" not in report_text:
        errors.append("bloco CONTROLS-SUMMARY ausente no relatório")
    if GENERATOR_PLACEHOLDER in report_text:
        errors.append("gerador nunca executado sobre este relatório (placeholder não substituído)")

    if any(pattern.search(report_text) for pattern in PROHIBITED_COVERAGE_SCALAR_PATTERNS):
        errors.append(
            "escalar agregado de cobertura regulatória proibido: publique o vetor de estados "
            "até o eixo normativo vigente estar integralmente modelado e avaliado"
        )

    narrative_pending = len(NARRATIVE_PLACEHOLDER_PATTERN.findall(report_text))
    if narrative_pending:
        warnings.append(f"{narrative_pending} seção(ões) narrativa(s) ainda não preenchida(s) por humano")

    designation = parse_designation(designation_text)
    status = designation.get("status")
    if status not in VALID_DESIGNATION_STATUS:
        errors.append(f"status de designação executiva inválido ou ausente: {status}")
    elif status == "pending_formal_designation":
        warnings.append(
            "responsável executivo ainda não designado formalmente — "
            "controle não pode ser declarado 'implemented' enquanto isso persistir"
        )

    return {
        "schema_version": "1.1.0",
        "control_id": "BACEN-08",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "summary": {
            "executive_designation_status": status,
            "narrative_sections_pending": narrative_pending,
            "coverage_scalar_present": any(
                pattern.search(report_text) for pattern in PROHIBITED_COVERAGE_SCALAR_PATTERNS
            ),
        },
        "errors": errors,
        "warnings": warnings,
        "result": "invalid" if errors else "valid_with_pending_items" if warnings else "valid",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="governance/bacen/ANNUAL-CYBERSECURITY-REPORT.md")
    parser.add_argument("--designation", default="governance/bacen/EXECUTIVE-DESIGNATION.yaml")
    parser.add_argument("--output", default="artifacts/bacen/bacen-08-annual-report-check.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    report_path = root / args.report
    designation_path = root / args.designation
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    if not report_path.exists() or not designation_path.exists():
        missing = [str(p) for p in (report_path, designation_path) if not p.exists()]
        report: dict[str, object] = {"result": "invalid", "errors": [f"arquivo ausente: {m}" for m in missing]}
    else:
        report = validate(
            report_path.read_text(encoding="utf-8"), designation_path.read_text(encoding="utf-8")
        )

    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report.get("summary", report), ensure_ascii=False))

    return 1 if report.get("result") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
