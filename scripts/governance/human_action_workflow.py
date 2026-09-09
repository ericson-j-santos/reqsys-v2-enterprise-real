#!/usr/bin/env python3
"""Gerencia pendências humanas governadas do ReqSys.

O módulo usa apenas a biblioteca padrão. Ele não executa ações privilegiadas nem
aceita segredos como evidência: valida somente metadados e referências
rastreáveis produzidas pelos responsáveis humanos e pelas automações do ReqSys.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "governance" / "human-actions" / "catalog.json"
ALLOWED_STATUSES = {
    "awaiting_human_action",
    "evidence_received",
    "validation_failed",
    "validated",
}


class HumanActionError(ValueError):
    """Erro de contrato do fluxo de ação humana."""


@dataclass(frozen=True)
class ValidationResult:
    action_id: str
    status: str
    valid: bool
    errors: list[str]
    missing_evidence: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "status": self.status,
            "valid": self.valid,
            "errors": self.errors,
            "missing_evidence": self.missing_evidence,
        }


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HumanActionError(f"arquivo não encontrado: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HumanActionError(f"JSON inválido em {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise HumanActionError(f"objeto JSON esperado em {path}")
    return data


def load_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    catalog = load_json(path)
    items = catalog.get("items")
    if not isinstance(items, list) or not items:
        raise HumanActionError("catalog.items deve ser uma lista não vazia")

    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise HumanActionError(f"catalog.items[{index}] deve ser objeto")
        action_id = item.get("id")
        if not isinstance(action_id, str) or not action_id:
            raise HumanActionError(f"catalog.items[{index}].id é obrigatório")
        if action_id in seen:
            raise HumanActionError(f"id duplicado no catálogo: {action_id}")
        seen.add(action_id)
        if item.get("status") not in ALLOWED_STATUSES:
            raise HumanActionError(f"status inválido em {action_id}: {item.get('status')}")
        for field in ("title", "owner_role", "requested_actions", "required_evidence", "completion_rules"):
            if field not in item:
                raise HumanActionError(f"campo obrigatório ausente em {action_id}: {field}")
    return catalog


def find_action(catalog: dict[str, Any], action_id: str) -> dict[str, Any]:
    for item in catalog["items"]:
        if item["id"] == action_id:
            return item
    raise HumanActionError(f"ação não cadastrada: {action_id}")


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        lowered = stripped.lower()
        if lowered in {"secret", "password", "senha", "token", "client_secret"}:
            return False
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _rule_error(rule: dict[str, Any], evidence: dict[str, Any]) -> str | None:
    kind = rule.get("kind")
    field = rule.get("field")
    if not isinstance(field, str) or not field:
        return "regra sem field válido"

    value = evidence.get(field)
    if kind == "present":
        return None if _has_value(value) else f"regra não atendida: {field} deve estar presente"
    if kind == "equals":
        expected = rule.get("value")
        return None if value == expected else f"regra não atendida: {field} deve ser {expected!r}"
    if kind == "not_equals":
        forbidden = rule.get("value")
        return None if value != forbidden else f"regra não atendida: {field} não pode ser {forbidden!r}"
    if kind == "one_of":
        allowed = rule.get("values")
        if not isinstance(allowed, list) or not allowed:
            return f"regra inválida para {field}: values deve ser lista não vazia"
        return None if value in allowed else f"regra não atendida: {field} deve pertencer a {allowed!r}"
    return f"tipo de regra desconhecido em {field}: {kind!r}"


def validate_evidence(action: dict[str, Any], evidence: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    missing: list[str] = []

    if evidence.get("action_id") != action["id"]:
        errors.append(f"action_id esperado {action['id']!r}")

    supplied_status = evidence.get("status", "evidence_received")
    if supplied_status not in ALLOWED_STATUSES:
        errors.append(f"status de evidência inválido: {supplied_status!r}")

    evidence_values = evidence.get("evidence")
    if not isinstance(evidence_values, dict):
        errors.append("evidence deve ser objeto")
        evidence_values = {}

    for key in action["required_evidence"]:
        if not _has_value(evidence_values.get(key)):
            missing.append(key)

    for rule in action["completion_rules"]:
        error = _rule_error(rule, evidence_values)
        if error:
            errors.append(error)

    valid = not errors and not missing
    status = "validated" if valid else "validation_failed"
    return ValidationResult(action["id"], status, valid, errors, missing)


def render_blueprint(action: dict[str, Any]) -> str:
    lines = [
        f"# Blueprint humano — {action['id']} — {action['title']}",
        "",
        f"- Prioridade: **{action['priority']}**",
        f"- WSJF: **{action.get('wsjf', 'n/a')}**",
        f"- Estado: **{action['status']}**",
        f"- Papel responsável: **{action['owner_role']}**",
        f"- Bloqueante: **{'sim' if action.get('blocking') else 'não'}**",
        "",
        "## Ações solicitadas",
    ]
    lines.extend(f"- {step}" for step in action["requested_actions"])
    lines.extend(["", "## Evidências obrigatórias"])
    lines.extend(f"- `{key}`" for key in action["required_evidence"])
    lines.extend(["", "## Critério de conclusão"])
    lines.extend(f"- {rule.get('description', rule)}" for rule in action["completion_rules"])
    if action.get("dependency"):
        lines.extend(["", "## Dependência", action["dependency"]])
    if action.get("verification"):
        lines.extend(["", "## Conclusão verificável", action["verification"]])
    return "\n".join(lines) + "\n"


def validate_catalog_command(catalog: dict[str, Any]) -> int:
    print(json.dumps({"valid": True, "items": len(catalog["items"]), "version": catalog.get("version")}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Governança de ações humanas do ReqSys")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate-catalog")

    blueprint = sub.add_parser("blueprint")
    blueprint.add_argument("action_id")
    blueprint.add_argument("--output", type=Path)

    validate = sub.add_parser("validate-evidence")
    validate.add_argument("action_id")
    validate.add_argument("evidence_file", type=Path)
    validate.add_argument("--output", type=Path)

    args = parser.parse_args(argv)
    try:
        catalog = load_catalog(args.catalog)
        if args.command == "validate-catalog":
            return validate_catalog_command(catalog)

        action = find_action(catalog, args.action_id)
        if args.command == "blueprint":
            rendered = render_blueprint(action)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered, encoding="utf-8")
            else:
                print(rendered, end="")
            return 0

        evidence = load_json(args.evidence_file)
        result = validate_evidence(action, evidence)
        payload = json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
        return 0 if result.valid else 2
    except HumanActionError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
