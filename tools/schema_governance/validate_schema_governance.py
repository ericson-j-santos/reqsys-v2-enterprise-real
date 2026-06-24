#!/usr/bin/env python3
"""ReqSys transversal schema governance validator.

This gate intentionally uses only the Python standard library so it can run in
GitHub Actions without adding product runtime dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
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
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


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


def load_json_from_git(ref: str, path: str) -> dict[str, Any] | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {ref}:{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {ref}:{path}")
    return value


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def get_schema_version(schema: dict[str, Any]) -> str | None:
    value = schema.get("properties", {}).get("schema_version", {}).get("const")
    return value if isinstance(value, str) else None


def parse_semver(version: str | None) -> tuple[int, int, int] | None:
    if not version:
        return None
    match = SEMVER_RE.match(version)
    if not match:
        return None
    return tuple(int(group) for group in match.groups())


def is_major_bump(old_version: str | None, new_version: str | None) -> bool:
    old = parse_semver(old_version)
    new = parse_semver(new_version)
    if old is None or new is None:
        return False
    return new[0] > old[0]


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
        if parse_semver(schema_version.get("const")) is None:
            errors.append(f"{location}: schema_version const must be SemVer, e.g. 1.0.0")

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


def schema_properties(schema: dict[str, Any]) -> dict[str, Any]:
    value = schema.get("properties")
    return value if isinstance(value, dict) else {}


def schema_required(schema: dict[str, Any]) -> set[str]:
    value = schema.get("required")
    return set(value) if isinstance(value, list) else set()


def flatten_object_schemas(schema: dict[str, Any], prefix: str = "$") -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    if schema.get("type") == "object":
        nodes[prefix] = schema
        for key, nested in schema_properties(schema).items():
            if isinstance(nested, dict):
                nodes.update(flatten_object_schemas(nested, f"{prefix}.{key}"))
    elif schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        nodes.update(flatten_object_schemas(schema["items"], f"{prefix}[]"))
    return nodes


def detect_breaking_changes(old_schema: dict[str, Any], new_schema: dict[str, Any], path: str) -> list[str]:
    changes: list[str] = []
    old_objects = flatten_object_schemas(old_schema)
    new_objects = flatten_object_schemas(new_schema)

    for location, old_object in old_objects.items():
        new_object = new_objects.get(location)
        if not new_object:
            changes.append(f"{path}: object schema removed at {location}")
            continue

        old_props = schema_properties(old_object)
        new_props = schema_properties(new_object)
        removed_props = sorted(set(old_props) - set(new_props))
        for prop in removed_props:
            changes.append(f"{path}: property removed at {location}.{prop}")

        old_required = schema_required(old_object)
        new_required = schema_required(new_object)
        added_required = sorted(new_required - old_required)
        for prop in added_required:
            changes.append(f"{path}: required property added at {location}.{prop}")

        if old_object.get("additionalProperties") is False and new_object.get("additionalProperties") is not False:
            changes.append(f"{path}: additionalProperties was relaxed at {location}")

        for prop in sorted(set(old_props) & set(new_props)):
            old_prop = old_props[prop]
            new_prop = new_props[prop]
            if not isinstance(old_prop, dict) or not isinstance(new_prop, dict):
                continue
            field = f"{location}.{prop}"
            if old_prop.get("type") != new_prop.get("type"):
                changes.append(f"{path}: type changed at {field}: {old_prop.get('type')} -> {new_prop.get('type')}")
            old_enum = old_prop.get("enum")
            new_enum = new_prop.get("enum")
            if isinstance(old_enum, list) and isinstance(new_enum, list):
                removed_enum = sorted(set(old_enum) - set(new_enum))
                if removed_enum:
                    changes.append(f"{path}: enum values removed at {field}: {', '.join(map(str, removed_enum))}")
            if "const" in old_prop and old_prop.get("const") != new_prop.get("const") and prop != "schema_version":
                changes.append(f"{path}: const changed at {field}")

    return changes


def validate_breaking_changes(registry: dict[str, Any], base_ref: str | None) -> tuple[list[str], list[str]]:
    if not base_ref:
        return [], ["| base/head breaking change detector | skipped | No base ref provided |"]

    errors: list[str] = []
    rows: list[str] = []
    schemas = registry.get("schemas", [])
    if not isinstance(schemas, list):
        return ["registry: schemas must be a list for breaking change detection"], rows

    for entry in schemas:
        if not isinstance(entry, dict) or not isinstance(entry.get("schema_path"), str):
            continue
        path = entry["schema_path"]
        old_schema = load_json_from_git(base_ref, path)
        if old_schema is None:
            rows.append(f"| {path} | new schema | No base contract found |")
            continue
        new_schema = load_json(ROOT / path)
        changes = detect_breaking_changes(old_schema, new_schema, path)
        old_version = get_schema_version(old_schema)
        new_version = get_schema_version(new_schema)
        if changes and not is_major_bump(old_version, new_version):
            errors.append(
                f"{path}: breaking changes require MAJOR schema_version bump "
                f"({old_version} -> {new_version}): " + "; ".join(changes)
            )
        elif changes:
            rows.append(f"| {path} | breaking accepted | MAJOR bump {old_version} -> {new_version} |")
        else:
            rows.append(f"| {path} | compatible | {old_version} -> {new_version} |")
    return errors, rows


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


def write_report(registry_rows: list[str], breaking_rows: list[str], errors: list[str]) -> None:
    status = "FAILED" if errors else "PASSED"
    lines = [
        "# Schema Governance Gate",
        "",
        f"Status: {status}",
        "",
        "## Registry Validation",
        "",
        "| Domain | Schema | Version | Registry Status |",
        "|---|---|---:|---|",
        *registry_rows,
        "",
        "## Breaking Change Detection",
        "",
        "| Contract | Result | Detail |",
        "|---|---|---|",
        *breaking_rows,
        "",
        "## Errors",
    ]
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- None")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate ReqSys governed schemas")
    parser.add_argument("--base-ref", default=None, help="Git ref used as compatibility baseline")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        registry = load_json(REGISTRY_PATH)
        registry_errors, registry_rows = validate_registry(registry)
        breaking_errors, breaking_rows = validate_breaking_changes(registry, args.base_ref)
        errors = registry_errors + breaking_errors
    except ValueError as exc:
        errors, registry_rows, breaking_rows = [str(exc)], [], []

    write_report(registry_rows, breaking_rows, errors)
    if errors:
        print("Schema governance validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Schema governance validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
