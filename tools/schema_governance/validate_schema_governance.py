#!/usr/bin/env python3
"""ReqSys transversal schema governance validator.

This gate intentionally uses only the Python standard library so it can run in
GitHub Actions without adding product runtime dependencies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "docs" / "schema-registry.json"
REPORT_PATH = ROOT / "schema-governance-report.md"
REQUIRED_GATES = {
    "schema_contract_gate",
    "schema_version_gate",
    "example_validation_gate",
    "breaking_change_gate",
    "additional_properties_gate",
    "required_fields_gate",
    "enum_evolution_gate",
    "contract_registry_gate",
    "ci_artifact_gate",
    "runtime_validation_gate",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"file not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def validate_schema_document(schema: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    location = rel(path)

    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append(f"{location}: $schema must use draft 2020-12")
    if not isinstance(schema.get("$id"), str) or not schema.get("$id"):
        errors.append(f"{location}: $id is required")
    if not isinstance(schema.get("title"), str) or not schema.get("title"):
        errors.append(f"{location}: title is required")
    if schema.get("type") != "object":
        errors.append(f"{location}: root type must be object")

    props = schema.get("properties")
    if not isinstance(props, dict):
        errors.append(f"{location}: properties must be declared")
        return errors

    schema_version = props.get("schema_version")
    if not isinstance(schema_version, dict):
        errors.append(f"{location}: properties.schema_version is required")
    else:
        if schema_version.get("type") != "string":
            errors.append(f"{location}: schema_version must be a string")
        if "const" not in schema_version:
            errors.append(f"{location}: schema_version must use const for deterministic versioning")

    required = schema.get("required")
    if not isinstance(required, list) or "schema_version" not in required:
        errors.append(f"{location}: schema_version must be required")

    errors.extend(validate_additional_properties(schema, location))
    return errors


def validate_additional_properties(node: Any, location: str) -> list[str]:
    errors: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "object" and node.get("additionalProperties") is not False:
            errors.append(f"{location}: every object schema must declare additionalProperties=false")
        for key, value in node.items():
            child_location = f"{location}.{key}"
            errors.extend(validate_additional_properties(value, child_location))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            errors.extend(validate_additional_properties(value, f"{location}[{index}]"))
    return errors


def validate_value(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")

    if expected_type == "object":
        if not isinstance(value, dict):
            return [f"{path}: expected object"]
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{path}.{key}: required field is missing")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, nested in properties.items():
                if key in value and isinstance(nested, dict):
                    errors.extend(validate_value(value[key], nested, f"{path}.{key}"))
            if schema.get("additionalProperties") is False:
                extra = sorted(set(value) - set(properties))
                for key in extra:
                    errors.append(f"{path}.{key}: additional property is not allowed")

    elif expected_type == "array":
        if not isinstance(value, list):
            return [f"{path}: expected array"]
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_value(item, item_schema, f"{path}[{index}]"))

    elif expected_type == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string")
        elif "minLength" in schema and len(value) < int(schema["minLength"]):
            errors.append(f"{path}: string is shorter than minLength")

    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{path}: expected number")
        else:
            if "minimum" in schema and value < schema["minimum"]:
                errors.append(f"{path}: number is below minimum")
            if "maximum" in schema and value > schema["maximum"]:
                errors.append(f"{path}: number is above maximum")

    elif expected_type == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{path}: expected boolean")

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is outside enum")

    return errors


def validate_registry(registry: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    report: list[str] = []

    gates = set(registry.get("governance", {}).get("required_gates", []))
    missing_gates = sorted(REQUIRED_GATES - gates)
    if missing_gates:
        errors.append("registry: missing required gates: " + ", ".join(missing_gates))

    schemas = registry.get("schemas")
    if not isinstance(schemas, list) or not schemas:
        errors.append("registry: schemas must be a non-empty list")
        return errors, report

    registered_paths = set()
    for entry in schemas:
        if not isinstance(entry, dict):
            errors.append("registry: every schema entry must be an object")
            continue

        schema_path = entry.get("schema_path")
        if not isinstance(schema_path, str):
            errors.append("registry: schema_path is required")
            continue
        registered_paths.add(schema_path)
        schema_file = ROOT / schema_path
        try:
            schema = load_json(schema_file)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        errors.extend(validate_schema_document(schema, schema_file))
        declared = schema.get("properties", {}).get("schema_version", {}).get("const")
        if declared != entry.get("version"):
            errors.append(f"{schema_path}: registry version must match schema_version const")
        if entry.get("breaking_change_policy") != "major_version_required":
            errors.append(f"{schema_path}: breaking_change_policy must be major_version_required")
        if entry.get("runtime_validation_required") is not True:
            errors.append(f"{schema_path}: runtime_validation_required must be true")
        if entry.get("ci_validation_required") is not True:
            errors.append(f"{schema_path}: ci_validation_required must be true")

        for example_path in entry.get("valid_examples", []):
            example_file = ROOT / example_path
            try:
                example = load_json(example_file)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            validation_errors = validate_value(example, schema, example_path)
            if validation_errors:
                errors.append(f"{example_path}: valid example failed: {'; '.join(validation_errors)}")

        for example_path in entry.get("invalid_examples", []):
            example_file = ROOT / example_path
            try:
                example = load_json(example_file)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            validation_errors = validate_value(example, schema, example_path)
            if not validation_errors:
                errors.append(f"{example_path}: invalid example unexpectedly passed")

        report.append(f"| {entry.get('domain')} | {entry.get('name')} | {entry.get('version')} | OK |")

    schema_files = {rel(path) for path in (ROOT / "schemas").rglob("*.schema.json")}
    unregistered = sorted(schema_files - registered_paths)
    for path in unregistered:
        errors.append(f"{path}: schema file is not registered in docs/schema-registry.json")

    return errors, report


def write_report(rows: list[str], errors: list[str]) -> None:
    status = "FAILED" if errors else "PASSED"
    lines = [
        "# Schema Governance Gate",
        "",
        f"Status: {status}",
        "",
        "| Domain | Schema | Version | Registry Status |",
        "|---|---|---:|---|",
        *rows,
        "",
        "## Errors",
    ]
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- None")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    try:
        registry = load_json(REGISTRY_PATH)
        errors, rows = validate_registry(registry)
    except ValueError as exc:
        errors, rows = [str(exc)], []

    write_report(rows, errors)
    if errors:
        print("Schema governance validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Schema governance validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
