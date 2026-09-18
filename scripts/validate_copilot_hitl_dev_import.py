from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

FORBIDDEN_ENVIRONMENT_TOKENS = ("prod", "production", "prd", "stg", "stage", "staging", "homolog")
PLACEHOLDER_PATTERN = re.compile(r"^(?:|changeme|todo|replace[_-]?me|<.*>|\$\{.*\})$", re.IGNORECASE)


def _is_placeholder(value: object) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    return bool(PLACEHOLDER_PATTERN.fullmatch(value.strip()))


def validate_environment_url(environment_url: str) -> None:
    parsed = urlparse(environment_url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("POWER_PLATFORM_ENVIRONMENT_URL deve ser uma URL HTTPS válida.")

    normalized = f"{parsed.netloc}{parsed.path}".lower()
    if any(token in normalized for token in FORBIDDEN_ENVIRONMENT_TOKENS):
        raise ValueError("Importação bloqueada: o destino informado não é reconhecido como DEV.")


def validate_package(package_path: Path) -> None:
    if not package_path.is_file():
        raise ValueError(f"Pacote não encontrado: {package_path}")
    if package_path.suffix.lower() != ".zip":
        raise ValueError("O pacote da Solution deve ser um arquivo ZIP.")
    if package_path.stat().st_size == 0:
        raise ValueError("O pacote da Solution está vazio.")


def validate_deployment_settings(settings_path: Path) -> dict:
    if not settings_path.is_file():
        raise ValueError(f"Deployment settings não encontrado: {settings_path}")

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Deployment settings inválido: {exc}") from exc

    connection_references = payload.get("ConnectionReferences")
    environment_variables = payload.get("EnvironmentVariables")
    if not isinstance(connection_references, list) or not connection_references:
        raise ValueError("ConnectionReferences deve conter ao menos uma referência.")
    if not isinstance(environment_variables, list) or not environment_variables:
        raise ValueError("EnvironmentVariables deve conter ao menos uma variável.")

    errors: list[str] = []
    for index, item in enumerate(connection_references):
        logical_name = item.get("LogicalName") or item.get("SchemaName") or f"índice {index}"
        connection_id = item.get("ConnectionId")
        connector_id = item.get("ConnectorId")
        if _is_placeholder(connection_id):
            errors.append(f"ConnectionId ausente para {logical_name}")
        if _is_placeholder(connector_id):
            errors.append(f"ConnectorId ausente para {logical_name}")

    for index, item in enumerate(environment_variables):
        schema_name = item.get("SchemaName") or f"índice {index}"
        if _is_placeholder(item.get("Value")):
            errors.append(f"Value ausente para {schema_name}")

    if errors:
        raise ValueError("Deployment settings incompleto: " + "; ".join(errors))

    return payload


def validate_import_inputs(package_path: Path, settings_path: Path, environment_url: str) -> dict:
    validate_environment_url(environment_url)
    validate_package(package_path)
    return validate_deployment_settings(settings_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Valida guardrails para importação ReqSys Copilot HITL em DEV.")
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--settings", required=True, type=Path)
    parser.add_argument("--environment-url", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        payload = validate_import_inputs(args.package, args.settings, args.environment_url)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1

    print(
        json.dumps(
            {
                "status": "validated",
                "target": "dev",
                "connection_references": len(payload["ConnectionReferences"]),
                "environment_variables": len(payload["EnvironmentVariables"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
