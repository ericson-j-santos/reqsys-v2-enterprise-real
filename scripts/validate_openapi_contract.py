#!/usr/bin/env python3
"""Validador governado do contrato OpenAPI ReqSys.

Escopo P0:
- Sem dependências externas.
- Valida JSON parse.
- Valida campos mínimos OpenAPI.
- Valida paths críticos runtime/requisitos.
- Emite artifact JSON para evidência CI.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

REQUIRED_PATHS = (
    "/api/requisitos/{id}",
    "/api/requisitos",
    "/api/runtime/health",
    "/api/runtime/dashboard",
    "/api/runtime/analytics",
)

REQUIRED_COMPONENT_SCHEMAS = (
    "RequisitoCreateRequest",
    "RequisitoResponse",
    "RequisitoCreateResponse",
    "Metadata",
)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("OpenAPI root must be a JSON object")
    return payload


def _has_operation(path_item: Any) -> bool:
    if not isinstance(path_item, dict):
        return False
    return any(method in path_item for method in ("get", "post", "put", "patch", "delete"))


def validate_contract(contract_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        payload = _load_json(contract_path)
    except Exception as exc:  # noqa: BLE001 - artifact deve capturar erro explícito
        return {
            "schema_version": "1.0.0",
            "contract": "reqsys-openapi-contract-validation",
            "validated_at_epoch": int(time.time()),
            "source": str(contract_path),
            "status": "failed",
            "errors": [f"json_parse_failed: {exc}"],
            "warnings": [],
            "summary": {"valid": False, "paths": 0, "schemas": 0},
        }

    openapi_version = payload.get("openapi")
    if not isinstance(openapi_version, str) or not openapi_version.startswith("3."):
        errors.append("openapi_version_must_start_with_3")

    info = payload.get("info")
    if not isinstance(info, dict):
        errors.append("info_object_missing")
    else:
        if not info.get("title"):
            errors.append("info_title_missing")
        if not info.get("version"):
            errors.append("info_version_missing")

    paths = payload.get("paths")
    if not isinstance(paths, dict) or not paths:
        errors.append("paths_object_missing_or_empty")
        paths = {}

    for required_path in REQUIRED_PATHS:
        if required_path not in paths:
            errors.append(f"required_path_missing:{required_path}")
        elif not _has_operation(paths[required_path]):
            errors.append(f"required_path_without_operation:{required_path}")

    components = payload.get("components")
    schemas: dict[str, Any] = {}
    if isinstance(components, dict) and isinstance(components.get("schemas"), dict):
        schemas = components["schemas"]
    else:
        errors.append("components_schemas_missing")

    for schema_name in REQUIRED_COMPONENT_SCHEMAS:
        if schema_name not in schemas:
            errors.append(f"required_schema_missing:{schema_name}")

    servers = payload.get("servers")
    if not isinstance(servers, list) or not servers:
        warnings.append("servers_missing_or_empty")

    tags = payload.get("tags")
    if not isinstance(tags, list) or not tags:
        warnings.append("tags_missing_or_empty")

    status = "passed" if not errors else "failed"
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-openapi-contract-validation",
        "validated_at_epoch": int(time.time()),
        "source": str(contract_path),
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "valid": status == "passed",
            "openapi_version": openapi_version,
            "info_version": info.get("version") if isinstance(info, dict) else None,
            "paths": len(paths),
            "schemas": len(schemas),
            "required_paths": len(REQUIRED_PATHS),
            "required_schemas": len(REQUIRED_COMPONENT_SCHEMAS),
        },
        "guardrails": [
            "no_external_dependencies",
            "json_parse_required",
            "required_runtime_paths_checked",
            "required_component_schemas_checked",
            "ci_artifact_enabled",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida contrato OpenAPI ReqSys")
    parser.add_argument(
        "--contract",
        default="docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json",
        help="Caminho do contrato OpenAPI JSON",
    )
    parser.add_argument(
        "--output",
        default="artifacts/openapi/openapi-contract-validation.json",
        help="Caminho do artifact de validação",
    )
    args = parser.parse_args()

    contract_path = Path(args.contract)
    report = validate_contract(contract_path)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
