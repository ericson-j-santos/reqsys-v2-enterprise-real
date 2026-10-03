#!/usr/bin/env python3
"""Valida o Credential & Environment Control Plane do ReqSys.

A validação é deliberadamente sem dependências externas. Ela garante que:
- nenhum valor secreto seja versionado no catálogo;
- ambientes e consumidores estejam alinhados ao manifesto Fly canônico;
- bindings referenciem credenciais existentes;
- todo material requerido por ambiente no manifesto Fly possua binding catalogado;
- o lifecycle use somente estados permitidos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTROL_PLANE = ROOT / "config" / "credential-control-plane.json"
DEFAULT_ENVIRONMENTS = ROOT / "infra" / "fly-environments.json"

FORBIDDEN_VALUE_KEYS = {
    "value",
    "secret_value",
    "token_value",
    "password",
    "private_key",
    "client_secret",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: raiz JSON deve ser objeto")
    return data


def walk_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key.lower() in FORBIDDEN_VALUE_KEYS:
                findings.append(child_path)
            findings.extend(walk_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(walk_forbidden_keys(child, f"{path}[{index}]"))
    return findings


def validate(control_plane: dict[str, Any], environments: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    principles = control_plane.get("principles", {})
    if principles.get("stores_secret_values") is not False:
        errors.append("principles.stores_secret_values deve ser false")

    forbidden = walk_forbidden_keys(control_plane)
    if forbidden:
        errors.append("campos de valor secreto proibidos: " + ", ".join(forbidden))

    canonical_envs = set(environments.get("canonical_environments", []))
    environment_defs = environments.get("environments", {})
    if not canonical_envs or not isinstance(environment_defs, dict):
        errors.append("manifesto de ambientes canônico inválido")
        return errors

    allowed_status = set(control_plane.get("lifecycle", {}).get("allowed_status", []))
    credentials = control_plane.get("credentials", [])
    bindings = control_plane.get("bindings", [])
    providers = set(control_plane.get("providers", {}).keys())

    if not isinstance(credentials, list) or not credentials:
        errors.append("credentials deve conter ao menos uma entrada")
        return errors
    if not isinstance(bindings, list):
        errors.append("bindings deve ser uma lista")
        return errors

    credential_by_id: dict[str, dict[str, Any]] = {}
    for index, credential in enumerate(credentials):
        if not isinstance(credential, dict):
            errors.append(f"credentials[{index}] deve ser objeto")
            continue
        credential_id = str(credential.get("credential_id", "")).strip()
        if not credential_id:
            errors.append(f"credentials[{index}].credential_id ausente")
            continue
        if credential_id in credential_by_id:
            errors.append(f"credential_id duplicado: {credential_id}")
        credential_by_id[credential_id] = credential

        if credential.get("provider") not in providers:
            errors.append(f"{credential_id}: provider não catalogado")
        if credential.get("status") not in allowed_status:
            errors.append(f"{credential_id}: status inválido {credential.get('status')!r}")
        if not str(credential.get("secret_reference", "")).strip():
            errors.append(f"{credential_id}: secret_reference ausente")

    binding_keys: set[tuple[str, str, str]] = set()
    coverage: set[tuple[str, str]] = set()
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            errors.append(f"bindings[{index}] deve ser objeto")
            continue
        credential_id = str(binding.get("credential_id", "")).strip()
        environment = str(binding.get("environment", "")).strip()
        consumer = str(binding.get("consumer", "")).strip()

        if credential_id not in credential_by_id:
            errors.append(f"binding referencia credencial inexistente: {credential_id}")
            continue
        if environment not in canonical_envs:
            errors.append(f"{credential_id}: ambiente não canônico: {environment}")
            continue
        expected_consumer = environment_defs.get(environment, {}).get("api_app")
        if consumer != expected_consumer:
            errors.append(
                f"{credential_id}/{environment}: consumer={consumer!r}; esperado={expected_consumer!r}"
            )

        key = (credential_id, environment, consumer)
        if key in binding_keys:
            errors.append(f"binding duplicado: {credential_id}/{environment}/{consumer}")
        binding_keys.add(key)
        coverage.add((environment, str(credential_by_id[credential_id].get("secret_reference"))))

    for environment in sorted(canonical_envs):
        required_names = environment_defs.get(environment, {}).get("required_secret_names", [])
        for required_name in required_names:
            if (environment, required_name) not in coverage:
                errors.append(
                    f"material requerido sem binding: ambiente={environment} reference={required_name}"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-plane", type=Path, default=DEFAULT_CONTROL_PLANE)
    parser.add_argument("--environments", type=Path, default=DEFAULT_ENVIRONMENTS)
    args = parser.parse_args()

    try:
        control_plane = load_json(args.control_plane)
        environments = load_json(args.environments)
        errors = validate(control_plane, environments)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("Credential Control Plane inválido:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Credential Control Plane válido: catálogo sem valores secretos e bindings coerentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
