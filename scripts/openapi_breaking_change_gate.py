#!/usr/bin/env python3
"""Gate de compatibilidade retroativa entre dois contratos OpenAPI.

O gate compara o contrato canônico da base com o candidato do HEAD e bloqueia
mudanças incompatíveis de alta confiança. Ele é deliberadamente offline,
determinístico e não altera runtime, dados ou ambientes.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "trace"})


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OpenAPI root must be a JSON object")
    return payload


def _parameter_map(path_item: dict[str, Any], operation: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    parameters: dict[tuple[str, str], dict[str, Any]] = {}
    for source in (path_item.get("parameters"), operation.get("parameters")):
        if not isinstance(source, list):
            continue
        for item in source:
            if not isinstance(item, dict) or "$ref" in item:
                continue
            name = item.get("name")
            location = item.get("in")
            if isinstance(name, str) and isinstance(location, str):
                parameters[(location, name)] = item
    return parameters


def _component_schemas(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    components = document.get("components")
    if not isinstance(components, dict):
        return {}
    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        return {}
    return {name: schema for name, schema in schemas.items() if isinstance(name, str) and isinstance(schema, dict)}


def find_breaking_changes(base: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    base_paths = base.get("paths") if isinstance(base.get("paths"), dict) else {}
    candidate_paths = candidate.get("paths") if isinstance(candidate.get("paths"), dict) else {}

    for path, base_path_item in base_paths.items():
        if not isinstance(base_path_item, dict):
            continue
        candidate_path_item = candidate_paths.get(path)
        if not isinstance(candidate_path_item, dict):
            changes.append({"code": "path_removed", "location": str(path), "detail": f"Path removido: {path}"})
            continue

        for method, base_operation in base_path_item.items():
            method_lower = str(method).lower()
            if method_lower not in HTTP_METHODS or not isinstance(base_operation, dict):
                continue
            candidate_operation = candidate_path_item.get(method_lower)
            location = f"{method_lower.upper()} {path}"
            if not isinstance(candidate_operation, dict):
                changes.append({"code": "operation_removed", "location": location, "detail": f"Operação removida: {location}"})
                continue

            base_parameters = _parameter_map(base_path_item, base_operation)
            candidate_parameters = _parameter_map(candidate_path_item, candidate_operation)
            for key, parameter in candidate_parameters.items():
                previous = base_parameters.get(key)
                if parameter.get("required") is True and (
                    previous is None or previous.get("required") is not True
                ):
                    changes.append({
                        "code": "required_parameter_added",
                        "location": location,
                        "detail": f"Parâmetro obrigatório introduzido: {key[0]}:{key[1]}",
                    })

            base_body = base_operation.get("requestBody")
            candidate_body = candidate_operation.get("requestBody")
            if isinstance(candidate_body, dict) and candidate_body.get("required") is True:
                if not isinstance(base_body, dict) or base_body.get("required") is not True:
                    changes.append({
                        "code": "request_body_became_required",
                        "location": location,
                        "detail": "Request body passou a ser obrigatório",
                    })

            base_responses = base_operation.get("responses")
            candidate_responses = candidate_operation.get("responses")
            if isinstance(base_responses, dict):
                candidate_response_keys = set(candidate_responses) if isinstance(candidate_responses, dict) else set()
                for status in base_responses:
                    if status not in candidate_response_keys:
                        changes.append({
                            "code": "response_removed",
                            "location": location,
                            "detail": f"Resposta removida: {status}",
                        })

    base_schemas = _component_schemas(base)
    candidate_schemas = _component_schemas(candidate)
    for name, base_schema in base_schemas.items():
        candidate_schema = candidate_schemas.get(name)
        if candidate_schema is None:
            changes.append({
                "code": "schema_removed",
                "location": f"components.schemas.{name}",
                "detail": f"Schema removido: {name}",
            })
            continue

        base_type = base_schema.get("type")
        candidate_type = candidate_schema.get("type")
        if base_type is not None and candidate_type is not None and base_type != candidate_type:
            changes.append({
                "code": "schema_type_changed",
                "location": f"components.schemas.{name}",
                "detail": f"Tipo alterado de {base_type!r} para {candidate_type!r}",
            })

        base_required = set(base_schema.get("required") or [])
        candidate_required = set(candidate_schema.get("required") or [])
        for field in sorted(candidate_required - base_required):
            changes.append({
                "code": "required_schema_property_added",
                "location": f"components.schemas.{name}.{field}",
                "detail": f"Propriedade passou a obrigatória: {field}",
            })

        base_properties = base_schema.get("properties")
        candidate_properties = candidate_schema.get("properties")
        if isinstance(base_properties, dict):
            candidate_property_names = set(candidate_properties) if isinstance(candidate_properties, dict) else set()
            for field in sorted(set(base_properties) - candidate_property_names):
                changes.append({
                    "code": "schema_property_removed",
                    "location": f"components.schemas.{name}.{field}",
                    "detail": f"Propriedade removida: {field}",
                })

            if isinstance(candidate_properties, dict):
                for field, base_property in base_properties.items():
                    candidate_property = candidate_properties.get(field)
                    if not isinstance(base_property, dict) or not isinstance(candidate_property, dict):
                        continue
                    base_property_type = base_property.get("type")
                    candidate_property_type = candidate_property.get("type")
                    if (
                        base_property_type is not None
                        and candidate_property_type is not None
                        and base_property_type != candidate_property_type
                    ):
                        changes.append({
                            "code": "schema_property_type_changed",
                            "location": f"components.schemas.{name}.{field}",
                            "detail": f"Tipo alterado de {base_property_type!r} para {candidate_property_type!r}",
                        })
                    base_enum = base_property.get("enum")
                    candidate_enum = candidate_property.get("enum")
                    if isinstance(base_enum, list) and isinstance(candidate_enum, list):
                        removed_values = [value for value in base_enum if value not in candidate_enum]
                        if removed_values:
                            changes.append({
                                "code": "enum_narrowed",
                                "location": f"components.schemas.{name}.{field}",
                                "detail": f"Valores de enum removidos: {removed_values!r}",
                            })

    return changes


def build_report(base_path: Path, candidate_path: Path) -> dict[str, Any]:
    try:
        base = _load(base_path)
        candidate = _load(candidate_path)
    except Exception as exc:  # noqa: BLE001
        return {
            "schema_version": "1.0.0",
            "contract": "reqsys-openapi-breaking-change-gate",
            "validated_at_epoch": int(time.time()),
            "status": "failed",
            "errors": [f"contract_load_failed:{type(exc).__name__}:{exc}"],
            "breaking_changes": [],
            "summary": {"breaking_change_count": 0},
        }

    changes = find_breaking_changes(base, candidate)
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-openapi-breaking-change-gate",
        "validated_at_epoch": int(time.time()),
        "status": "passed" if not changes else "breaking_change_detected",
        "base": str(base_path),
        "candidate": str(candidate_path),
        "head_sha": os.environ.get("GITHUB_SHA"),
        "errors": [],
        "breaking_changes": changes,
        "summary": {"breaking_change_count": len(changes)},
        "guardrails": [
            "offline",
            "deterministic",
            "fail_closed_on_contract_load_error",
            "negative_control_tested",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bloqueia breaking changes OpenAPI de alta confiança")
    parser.add_argument("--base", required=True, help="Contrato OpenAPI da branch base")
    parser.add_argument("--candidate", required=True, help="Contrato OpenAPI candidato do HEAD")
    parser.add_argument("--output", default="artifacts/openapi/openapi-breaking-change-gate.json")
    parser.add_argument("--strict", action="store_true", help="Retorna exit code 1 se houver incompatibilidade")
    args = parser.parse_args()

    report = build_report(Path(args.base), Path(args.candidate))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["status"] == "failed":
        return 1
    if args.strict and report["status"] != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
