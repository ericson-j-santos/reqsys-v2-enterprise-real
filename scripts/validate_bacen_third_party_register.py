#!/usr/bin/env python3
"""Valida o registro BACEN-05 de nuvem/terceiros contra as variáveis reais do projeto.

O objetivo não é certificar risco de fornecedor (isso exige revisão humana), mas
garantir que o registro nunca fique desatualizado em relação às integrações
externas realmente configuráveis no projeto: toda variável de ambiente que aponta
para um serviço externo precisa estar coberta por uma entrada do registro, e toda
entrada do registro precisa referenciar variáveis que realmente existem.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

REQUIRED_PROVIDER_FIELDS = {
    "id",
    "provider",
    "category",
    "purpose",
    "config_source",
    "data_classification",
    "criticality",
    "risk_review_status",
    "dpa_status",
}
VALID_CRITICALITY = {"critical", "high", "medium", "low"}

# Padrão de nomes de variável em .env.example que indicam integração com serviço
# externo (nuvem/terceiro) e por isso devem estar cobertas pelo registro BACEN-05.
EXTERNAL_VAR_PATTERN = re.compile(
    r"^(AZURE_|TEAMS_BOT_|TEAMS_FLOW_BOT_|GITHUB_TOKEN|FIGMA_|REDMINE_|SSRS_|"
    r"GEMINI_API_KEY|GROQ_API_KEY|DATABASE_URL|OPERATIONAL_QUEUE_REDIS_URL)"
)
# Variáveis que casam com o padrão acima mas são internas ao ReqSys (não um
# terceiro/nuvem externo) e por isso ficam explicitamente fora do escopo do registro.
EXTERNAL_VAR_EXEMPTIONS = {
    "GITHUB_REDMINE_SYNC_ENABLED",
    "ENABLE_GITHUB_REDMINE_IMPORT",
}


def env_vars(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Z][A-Z0-9_]*)=", stripped)
        if match:
            names.add(match.group(1))
    return names


def parse_providers(text: str) -> list[dict[str, object]]:
    """Parser mínimo do subconjunto YAML usado neste registro (sem dependência externa)."""
    providers: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    list_field: str | None = None
    in_providers = False

    for raw_line in text.splitlines():
        if raw_line.strip() == "providers:":
            in_providers = True
            continue
        if not in_providers:
            continue

        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        item_match = re.match(r"^- id:\s*(.+)$", stripped)
        if item_match:
            if current:
                providers.append(current)
            current = {"id": item_match.group(1).strip()}
            list_field = None
            continue

        if current is None:
            continue

        list_item_match = re.match(r"^-\s*(.+)$", stripped)
        if list_item_match and list_field:
            current.setdefault(list_field, [])
            current[list_field].append(list_item_match.group(1).strip().strip('"\''))
            continue

        key_match = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", stripped)
        if key_match:
            key, value = key_match.group(1), key_match.group(2).strip()
            if value:
                current[key] = value.strip('"\'')
                list_field = None
            else:
                current[key] = []
                list_field = key

    if current:
        providers.append(current)
    return providers


def load_register(path: Path) -> dict[str, object]:
    return {"providers": parse_providers(path.read_text(encoding="utf-8"))}


def validate(root: Path, register_path: Path, env_path: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []

    register = load_register(register_path)
    providers = register.get("providers", [])
    if not isinstance(providers, list) or not providers:
        errors.append("O registro não contém provedores.")
        providers = []

    ids: set[str] = set()
    registered_vars: set[str] = set()
    for provider in providers:
        provider_id = provider.get("id", "UNKNOWN")
        missing = sorted(REQUIRED_PROVIDER_FIELDS - provider.keys())
        if missing:
            errors.append(f"{provider_id}: campos ausentes: {', '.join(missing)}")
        if provider_id in ids:
            errors.append(f"{provider_id}: identificador duplicado")
        ids.add(provider_id)
        if provider.get("criticality") not in VALID_CRITICALITY:
            errors.append(f"{provider_id}: criticidade inválida: {provider.get('criticality')}")
        config_source = provider.get("config_source") or []
        if not config_source:
            warnings.append(f"{provider_id}: nenhuma variável de configuração declarada")
        registered_vars.update(config_source)

    env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    declared_vars = env_vars(env_text)

    for var in registered_vars:
        if var not in declared_vars:
            errors.append(f"registro referencia variável inexistente em .env.example: {var}")

    external_vars = {
        var for var in declared_vars
        if EXTERNAL_VAR_PATTERN.match(var) and var not in EXTERNAL_VAR_EXEMPTIONS
    }
    undeclared = sorted(external_vars - registered_vars)
    for var in undeclared:
        errors.append(f"variável de integração externa sem entrada no registro BACEN-05: {var}")

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "summary": {
            "total_providers": len(providers),
            "registered_config_vars": len(registered_vars),
            "external_vars_detected": len(external_vars),
            "drift_detected": len(undeclared) > 0,
        },
        "errors": errors,
        "warnings": warnings,
        "result": "invalid" if errors else "valid",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", default="governance/bacen/CLOUD-THIRD-PARTY-REGISTER.yaml")
    parser.add_argument("--env-file", default=".env.example")
    parser.add_argument("--output", default="artifacts/bacen/bacen-05-third-party-drift-report.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    register_path = root / args.register
    env_path = root / args.env_file
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    if not register_path.exists():
        report: dict[str, object] = {
            "result": "invalid",
            "errors": [f"Registro ausente: {args.register}"],
        }
    else:
        report = validate(root, register_path, env_path)

    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report.get("summary", report), ensure_ascii=False))

    return 1 if report.get("result") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
