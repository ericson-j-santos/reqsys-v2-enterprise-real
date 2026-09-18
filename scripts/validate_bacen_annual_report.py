#!/usr/bin/env python3
"""Valida o contrato estrutural do relatório anual de segurança cibernética (BACEN-08).

Não declara conformidade e não substitui revisão humana. O validador garante que:
- o relatório existe e os blocos gerados automaticamente foram preenchidos;
- o registro de designação executiva existe e possui status reconhecido;
- o contrato mínimo do relatório anual possui todos os blocos normativos exigidos;
- blocos obrigatórios não estão ausentes nem vazios;
- toda publicação estrutural possui `as_of` em UTC/RFC 3339;
- nenhum escalar agregado de cobertura regulatória é publicado enquanto o eixo
  normativo vigente não estiver integralmente modelado e avaliado.

Conteúdo ainda não avaliado deve ser declarado explicitamente como tal. O gate
falha por ausência estrutural, não por inventar conformidade para preencher lacunas.
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
HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
AS_OF_PATTERN = re.compile(
    r"`as_of`\s*:\s*`(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)`"
)
PROHIBITED_COVERAGE_SCALAR_PATTERNS = (
    re.compile(r"Cobertura\s+ponderada\s*:\s*\*\*?\s*\d+(?:[.,]\d+)?%", re.IGNORECASE),
    re.compile(r"Cobertura\s+regulat[óo]ria\s*:\s*\*\*?\s*\d+(?:[.,]\d+)?%", re.IGNORECASE),
)

# Chaves estáveis para saída de máquina; valores aceitam aliases legados para
# preservar contratos existentes enquanto o vocabulário do relatório converge.
REQUIRED_CONTRACT_SECTIONS: dict[str, tuple[str, ...]] = {
    "baseline_normativa": ("Baseline normativa utilizada",),
    "incidentes_ciberneticos": (
        "Incidentes cibernéticos relevantes do período",
        "Incidentes de segurança do período",
    ),
    "continuidade_negocios": ("Resultados dos testes de continuidade de negócios",),
    "testes_intrusao": ("Resultados dos testes de intrusão",),
    "vulnerabilidades": ("Varreduras e análises de vulnerabilidades",),
    "planos_corretivos": (
        "Planos de ação para correções",
        "Plano de ação para o próximo ciclo",
    ),
}


def extract_sections(report_text: str) -> dict[str, str]:
    """Extrai seções de nível 2 sem interpretar conteúdo de negócio."""
    matches = list(HEADING_PATTERN.finditer(report_text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(report_text)
        sections[heading] = report_text[body_start:body_end].strip()
    return sections


def has_meaningful_body(body: str) -> bool:
    """Comentários HTML isolados não satisfazem bloco obrigatório."""
    without_comments = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    return bool(without_comments.strip())


def resolve_contract_sections(
    sections: dict[str, str],
) -> tuple[dict[str, str], list[str], list[str]]:
    resolved: dict[str, str] = {}
    missing: list[str] = []
    empty: list[str] = []

    for key, aliases in REQUIRED_CONTRACT_SECTIONS.items():
        heading = next((alias for alias in aliases if alias in sections), None)
        if heading is None:
            missing.append(key)
            continue
        resolved[key] = heading
        if not has_meaningful_body(sections[heading]):
            empty.append(key)

    return resolved, missing, empty


def extract_report_as_of(sections: dict[str, str]) -> str | None:
    baseline_body = sections.get("Baseline normativa utilizada", "")
    match = AS_OF_PATTERN.search(baseline_body)
    if not match:
        return None

    value = match.group(1)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        return None
    return value


def validate(report_text: str, designation_text: str) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []

    if "<!-- BACEN-08:EXECUTIVE:START -->" not in report_text:
        errors.append("bloco EXECUTIVE ausente no relatório")
    if "<!-- BACEN-08:CONTROLS-SUMMARY:START -->" not in report_text:
        errors.append("bloco CONTROLS-SUMMARY ausente no relatório")
    if GENERATOR_PLACEHOLDER in report_text:
        errors.append("gerador nunca executado sobre este relatório (placeholder não substituído)")

    coverage_scalar_present = any(
        pattern.search(report_text) for pattern in PROHIBITED_COVERAGE_SCALAR_PATTERNS
    )
    if coverage_scalar_present:
        errors.append(
            "escalar agregado de cobertura regulatória proibido: publique o vetor de estados "
            "até o eixo normativo vigente estar integralmente modelado e avaliado"
        )

    sections = extract_sections(report_text)
    resolved_sections, missing_sections, empty_sections = resolve_contract_sections(sections)
    if missing_sections:
        errors.append(
            "blocos obrigatórios do contrato normativo ausentes: " + ", ".join(missing_sections)
        )
    if empty_sections:
        errors.append(
            "blocos obrigatórios do contrato normativo vazios: " + ", ".join(empty_sections)
        )

    report_as_of = extract_report_as_of(sections)
    if report_as_of is None:
        errors.append(
            "baseline normativa sem `as_of` válido em UTC/RFC 3339; toda publicação de estado deve carimbar o instante de apuração"
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

    contract_complete = not missing_sections and not empty_sections and report_as_of is not None

    return {
        "schema_version": "1.2.0",
        "control_id": "BACEN-08",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "summary": {
            "executive_designation_status": status,
            "narrative_sections_pending": narrative_pending,
            "coverage_scalar_present": coverage_scalar_present,
            "contract_sections_required": len(REQUIRED_CONTRACT_SECTIONS),
            "contract_sections_resolved": resolved_sections,
            "contract_sections_missing": missing_sections,
            "contract_sections_empty": empty_sections,
            "report_as_of": report_as_of,
            "contract_complete": contract_complete,
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
        report: dict[str, object] = {
            "result": "invalid",
            "errors": [f"arquivo ausente: {m}" for m in missing],
        }
    else:
        report = validate(
            report_path.read_text(encoding="utf-8"), designation_path.read_text(encoding="utf-8")
        )

    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report.get("summary", report), ensure_ascii=False))

    return 1 if report.get("result") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
