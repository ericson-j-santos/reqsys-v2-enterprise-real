#!/usr/bin/env python3
"""Valida o contrato mínimo de governança de Issues do ReqSys.

O módulo não acessa a rede nem altera o GitHub. Ele recebe uma Issue em JSON
ou por argumentos explícitos e produz um resultado determinístico em JSON.
A automação GitHub Actions é responsável apenas por orquestrar eventos e
sincronizar o comentário de diagnóstico.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.1.0"
TITLE_PREFIX = "[ISSUE]"

# Painéis operacionais são Issues reescritas periodicamente por automação e não
# possuem autor humano responsável por preencher o contrato de rastreabilidade.
# Só ficam fora do contrato quando a automação marca o corpo e o autor é um bot.
OPERATIONAL_PANEL_MARKER = "<!-- reqsys-operational-panel -->"
SCOPE_GOVERNED_ISSUE = "governed_issue"
SCOPE_OPERATIONAL_PANEL = "operational_panel"
BOT_AUTHOR_TYPE = "bot"

REQUIRED_SECTIONS: tuple[str, ...] = (
    "Descrição do problema",
    "Estado atual evidenciado",
    "Estado esperado",
    "Causa raiz",
    "Critérios de aceite",
    "Riscos",
    "Dependências",
    "Evidências",
    "PR(s) relacionadas",
    "Responsável",
    "Prioridade",
    "Declaração de rastreabilidade",
)

HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
PRIORITY_RE = re.compile(r"\bP[0-3]\b", re.IGNORECASE)
CHECKED_BOX_RE = re.compile(r"\[[xX]\]")


@dataclass(frozen=True)
class FieldProblem:
    field: str
    reason: str


@dataclass(frozen=True)
class ValidationResult:
    schema_version: str
    issue_number: int | None
    scope: str
    valid: bool
    checked_fields: int
    missing_fields: list[str]
    invalid_fields: list[FieldProblem]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["invalid_fields"] = [asdict(item) for item in self.invalid_fields]
        return payload


def normalize_heading(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    alphanumeric = re.sub(r"[^a-zA-Z0-9]+", " ", without_accents).strip().lower()
    return re.sub(r"\s+", " ", alphanumeric)


def clean_section(value: str) -> str:
    return HTML_COMMENT_RE.sub("", value).strip()


def parse_sections(body: str) -> dict[str, str]:
    matches = list(HEADING_RE.finditer(body or ""))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        heading = normalize_heading(match.group(1))
        sections[heading] = clean_section(body[start:end])
    return sections


def is_operational_panel(*, body: str, author_type: str | None) -> bool:
    """Indica se a Issue é um painel operacional mantido por automação."""
    if OPERATIONAL_PANEL_MARKER not in (body or ""):
        return False
    return (author_type or "").strip().lower() == BOT_AUTHOR_TYPE


def meaningful_title(title: str) -> bool:
    candidate = (title or "").strip()
    if candidate.upper().startswith(TITLE_PREFIX):
        candidate = candidate[len(TITLE_PREFIX) :].strip()
    return bool(candidate)


def validate_issue(
    *,
    title: str,
    body: str,
    issue_number: int | None = None,
    author_type: str | None = None,
) -> ValidationResult:
    if is_operational_panel(body=body, author_type=author_type):
        return ValidationResult(
            schema_version=SCHEMA_VERSION,
            issue_number=issue_number,
            scope=SCOPE_OPERATIONAL_PANEL,
            valid=True,
            checked_fields=0,
            missing_fields=[],
            invalid_fields=[],
        )

    sections = parse_sections(body or "")
    missing_fields: list[str] = []
    invalid_fields: list[FieldProblem] = []

    if not meaningful_title(title):
        invalid_fields.append(FieldProblem("Título", "Informe um título objetivo além do prefixo [ISSUE]."))

    for label in REQUIRED_SECTIONS:
        key = normalize_heading(label)
        if key not in sections or not sections[key]:
            missing_fields.append(label)

    priority_key = normalize_heading("Prioridade")
    if priority_key in sections and sections[priority_key] and not PRIORITY_RE.search(sections[priority_key]):
        invalid_fields.append(FieldProblem("Prioridade", "Use uma prioridade válida entre P0 e P3."))

    declaration_key = normalize_heading("Declaração de rastreabilidade")
    if declaration_key in sections and sections[declaration_key] and not CHECKED_BOX_RE.search(sections[declaration_key]):
        invalid_fields.append(
            FieldProblem(
                "Declaração de rastreabilidade",
                "A declaração deve estar explicitamente marcada como confirmada ([x]).",
            )
        )

    valid = not missing_fields and not invalid_fields
    return ValidationResult(
        schema_version=SCHEMA_VERSION,
        issue_number=issue_number,
        scope=SCOPE_GOVERNED_ISSUE,
        valid=valid,
        checked_fields=1 + len(REQUIRED_SECTIONS),
        missing_fields=missing_fields,
        invalid_fields=invalid_fields,
    )


def _issue_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "issue" in payload and isinstance(payload["issue"], dict):
        payload = payload["issue"]
    return payload


def load_issue_author_type(path: Path) -> str | None:
    """Extrai o tipo do autor (``User``/``Bot``) do payload da Issue."""
    payload = _issue_payload(path)
    author_type = payload.get("author_type")
    if author_type is None and isinstance(payload.get("user"), dict):
        author_type = payload["user"].get("type")
    return str(author_type) if author_type is not None else None


def load_issue_json(path: Path) -> tuple[str, str, int | None]:
    payload = _issue_payload(path)

    title = str(payload.get("title") or "")
    body = str(payload.get("body") or "")
    number_raw = payload.get("number")
    issue_number = int(number_raw) if number_raw is not None else None
    return title, body, issue_number


def render_comment(result: ValidationResult) -> str:
    marker = "<!-- reqsys-issue-governance-validator -->"
    if result.scope == SCOPE_OPERATIONAL_PANEL:
        return "\n".join(
            (
                marker,
                "## Governança da Issue — fora de escopo",
                "",
                "Esta Issue é um painel operacional reescrito por automação e não está sujeita ao",
                "contrato mínimo de rastreabilidade de Issues governadas.",
                "",
                "O diagnóstico anterior deixou de valer. Nenhuma ação humana é necessária aqui.",
            )
        )

    if result.valid:
        return "\n".join(
            (
                marker,
                "## Governança da Issue — conforme",
                "",
                f"Validação automática concluída: **{result.checked_fields}/{result.checked_fields} campos válidos**.",
                "",
                "Esta Issue atende ao contrato mínimo de rastreabilidade do ReqSys.",
            )
        )

    lines = [
        marker,
        "## Governança da Issue — correção necessária",
        "",
        "A Issue não atende ao contrato mínimo de rastreabilidade. Corrija os itens abaixo; não invente evidências para satisfazer o validador.",
        "",
    ]
    if result.missing_fields:
        lines.extend(("### Campos ausentes ou vazios", *[f"- {item}" for item in result.missing_fields], ""))
    if result.invalid_fields:
        lines.append("### Campos inválidos")
        lines.extend(f"- **{item.field}:** {item.reason}" for item in result.invalid_fields)
        lines.append("")
    lines.extend(
        (
            "### Como regularizar",
            "Use o formulário **Issue governada** ou mantenha os mesmos títulos `###` no corpo criado por API/bot/automação.",
            "Quando algo ainda não existir, registre explicitamente `Não aplicável`, `Nenhuma` ou `Ainda desconhecida`, conforme o caso.",
        )
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--issue-json", type=Path, help="JSON contendo title/body/number ou payload com chave issue.")
    source.add_argument("--title", help="Título da Issue para validação direta.")
    parser.add_argument("--body", default="", help="Corpo da Issue quando --title for usado.")
    parser.add_argument("--number", type=int, default=None, help="Número opcional da Issue.")
    parser.add_argument(
        "--author-type",
        default=None,
        help="Tipo do autor da Issue (User/Bot). Prevalece sobre o valor presente no JSON.",
    )
    parser.add_argument("--comment-output", type=Path, default=None, help="Arquivo Markdown para comentário idempotente.")
    parser.add_argument("--json-output", type=Path, default=None, help="Arquivo adicional com o resultado JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.issue_json:
        title, body, issue_number = load_issue_json(args.issue_json)
        author_type = args.author_type or load_issue_author_type(args.issue_json)
    else:
        title, body, issue_number = args.title or "", args.body or "", args.number
        author_type = args.author_type

    result = validate_issue(
        title=title,
        body=body,
        issue_number=issue_number,
        author_type=author_type,
    )
    payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    print(payload)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload + "\n", encoding="utf-8")
    if args.comment_output:
        args.comment_output.parent.mkdir(parents=True, exist_ok=True)
        args.comment_output.write_text(render_comment(result) + "\n", encoding="utf-8")

    return 0 if result.valid else 2


if __name__ == "__main__":
    sys.exit(main())
