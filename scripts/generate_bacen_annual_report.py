#!/usr/bin/env python3
"""Regenera as seções derivadas do relatório anual de segurança cibernética (BACEN-08).

Este gerador NUNCA preenche nome/cargo de responsável executivo nem texto
narrativo — apenas atualiza, entre marcadores explícitos, dados objetivos que já
existem em outros arquivos versionados: o status real da designação executiva
(`EXECUTIVE-DESIGNATION.yaml`) e o panorama da matriz de controles
(`BACEN-CONTROL-MATRIX.yaml`). Tudo o que exige decisão humana permanece como
texto placeholder até revisão manual.

Importante: enquanto o eixo normativo vigente não estiver integralmente modelado
e avaliado, o gerador publica apenas o vetor de estados dos macrocontroles
internos. Ele não calcula nem publica percentual agregado de cobertura
regulatória.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.validate_bacen_controls import parse_controls  # noqa: E402

EXECUTIVE_START = "<!-- BACEN-08:EXECUTIVE:START -->"
EXECUTIVE_END = "<!-- BACEN-08:EXECUTIVE:END -->"
CONTROLS_START = "<!-- BACEN-08:CONTROLS-SUMMARY:START -->"
CONTROLS_END = "<!-- BACEN-08:CONTROLS-SUMMARY:END -->"


def parse_designation(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    in_block = False
    for raw_line in text.splitlines():
        if raw_line.strip() == "designation:":
            in_block = True
            continue
        if in_block:
            if raw_line.strip() and not raw_line.startswith((" ", "\t")):
                break
            match = re.match(r"^\s+([a-zA-Z0-9_]+):\s*(.*)$", raw_line)
            if match:
                key, value = match.group(1), match.group(2).strip().strip('"\'')
                fields[key] = value
    return fields


def render_executive_block(designation: dict[str, str]) -> str:
    executive_name = designation.get("executive_name")
    is_pending = not executive_name or executive_name == "null"
    if is_pending:
        return (
            f"{EXECUTIVE_START}\n"
            f"- Status da designação: `{designation.get('status', 'pending_formal_designation')}`\n"
            "- Nome: *(pendente de designação formal)*\n"
            "- Cargo: *(pendente de designação formal)*\n"
            f"{EXECUTIVE_END}"
        )
    return (
        f"{EXECUTIVE_START}\n"
        f"- Status da designação: `{designation.get('status')}`\n"
        f"- Nome: {designation.get('executive_name')}\n"
        f"- Cargo: {designation.get('executive_role', '(não informado)')}\n"
        f"- Designado em: {designation.get('designated_at', '(não informado)')}\n"
        f"- Documento de designação: {designation.get('designation_document_reference', '(não informado)')}\n"
        f"{EXECUTIVE_END}"
    )


def render_controls_block(controls: list[dict[str, str]]) -> str:
    """Renderiza somente o vetor de estados dos controles internos.

    Não publica percentual agregado. Os BACEN-01..08 são macrocontroles internos
    e não constituem, isoladamente, o denominador normativo vigente.
    """
    lines = [CONTROLS_START, ""]
    lines.append("| Controle interno | Domínio | Criticidade | Status |")
    lines.append("|---|---|---|---|")
    for control in controls:
        lines.append(
            f"| {control.get('id', '?')} | {control.get('domain', '?')} "
            f"| {control.get('criticality', '?')} | {control.get('status', '?')} |"
        )
    lines.append("")
    lines.append(
        "> **Nota:** estes são macrocontroles internos do ReqSys. "
        "Nenhum percentual agregado de cobertura regulatória é publicado enquanto "
        "o eixo normativo vigente não estiver integralmente modelado e avaliado."
    )
    lines.append(CONTROLS_END)
    return "\n".join(lines)


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL
    )
    if not pattern.search(text):
        raise ValueError(f"marcadores não encontrados no relatório: {start_marker} / {end_marker}")
    return pattern.sub(replacement, text, count=1)


def regenerate(report_text: str, matrix_text: str, designation_text: str) -> str:
    controls = parse_controls(matrix_text)
    designation = parse_designation(designation_text)

    updated = replace_block(
        report_text, EXECUTIVE_START, EXECUTIVE_END, render_executive_block(designation)
    )
    updated = replace_block(
        updated, CONTROLS_START, CONTROLS_END, render_controls_block(controls)
    )
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="governance/bacen/ANNUAL-CYBERSECURITY-REPORT.md")
    parser.add_argument("--matrix", default="governance/bacen/BACEN-CONTROL-MATRIX.yaml")
    parser.add_argument("--designation", default="governance/bacen/EXECUTIVE-DESIGNATION.yaml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    report_path = root / args.report
    matrix_path = root / args.matrix
    designation_path = root / args.designation

    for path in (report_path, matrix_path, designation_path):
        if not path.exists():
            print(f"arquivo ausente: {path}", file=sys.stderr)
            return 1

    updated = regenerate(
        report_path.read_text(encoding="utf-8"),
        matrix_path.read_text(encoding="utf-8"),
        designation_path.read_text(encoding="utf-8"),
    )
    report_path.write_text(updated, encoding="utf-8")
    print(f"relatório atualizado: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
