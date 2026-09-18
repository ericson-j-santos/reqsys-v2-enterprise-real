#!/usr/bin/env python3
"""ReqSys transversal schema governance validator.

This gate intentionally uses only the Python standard library so it can run in
GitHub Actions without adding product runtime dependencies.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "docs" / "schema-registry.json"
REPORT_PATH = ROOT / "schema-governance-report.md"
REPORT_JSON_PATH = ROOT / "schema-governance-report.json"
REPORT_HTML_PATH = ROOT / "schema-governance-report.html"
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


def percent(part: int, whole: int) -> int:
    if whole <= 0:
        return 100
    return round((part / whole) * 100)


def classify_risk(errors: list[str], runtime_coverage: int, example_coverage: int, breaking_rows: list[str]) -> str:
    if errors:
        return "critical"
    if runtime_coverage < 100 or example_coverage < 100:
        return "high"
    if any("skipped" in row for row in breaking_rows):
        return "medium"
    return "low"


def build_executive_report(
    registry: dict[str, Any],
    registry_rows: list[str],
    breaking_rows: list[str],
    errors: list[str],
    base_ref: str | None,
) -> dict[str, Any]:
    schemas = registry.get("schemas", []) if isinstance(registry.get("schemas"), list) else []
    gates = set(registry.get("governance", {}).get("required_gates", []))
    total_contracts = len(schemas)
    active_contracts = sum(1 for item in schemas if isinstance(item, dict) and item.get("status") == "active")
    runtime_required = sum(1 for item in schemas if isinstance(item, dict) and item.get("runtime_validation_required") is True)
    ci_required = sum(1 for item in schemas if isinstance(item, dict) and item.get("ci_validation_required") is True)
    with_valid_examples = sum(1 for item in schemas if isinstance(item, dict) and item.get("valid_examples"))
    with_invalid_examples = sum(1 for item in schemas if isinstance(item, dict) and item.get("invalid_examples"))
    runtime_coverage = percent(runtime_required, total_contracts)
    ci_coverage = percent(ci_required, total_contracts)
    valid_example_coverage = percent(with_valid_examples, total_contracts)
    invalid_example_coverage = percent(with_invalid_examples, total_contracts)
    example_coverage = min(valid_example_coverage, invalid_example_coverage)
    gate_coverage = percent(len(gates & REQUIRED_GATES), len(REQUIRED_GATES))
    success = not errors
    base_score = 100 if success else max(0, 100 - min(len(errors), 10) * 10)
    maturity_score = round(
        gate_coverage * 0.25
        + runtime_coverage * 0.20
        + ci_coverage * 0.15
        + example_coverage * 0.20
        + base_score * 0.20
    )
    risk_level = classify_risk(errors, runtime_coverage, example_coverage, breaking_rows)
    production_readiness = min(maturity_score, 100 if risk_level == "low" else 74 if risk_level == "medium" else 49)

    contract_rows = []
    for item in schemas:
        if not isinstance(item, dict):
            continue
        valid_examples = item.get("valid_examples") if isinstance(item.get("valid_examples"), list) else []
        invalid_examples = item.get("invalid_examples") if isinstance(item.get("invalid_examples"), list) else []
        contract_rows.append(
            {
                "domain": item.get("domain"),
                "name": item.get("name"),
                "version": item.get("version"),
                "status": item.get("status"),
                "schema_path": item.get("schema_path"),
                "runtime_validation_required": item.get("runtime_validation_required") is True,
                "ci_validation_required": item.get("ci_validation_required") is True,
                "valid_examples": len(valid_examples),
                "invalid_examples": len(invalid_examples),
                "breaking_change_policy": item.get("breaking_change_policy"),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED" if success else "FAILED",
        "base_ref": base_ref,
        "summary": {
            "maturity_score": maturity_score,
            "risk_level": risk_level,
            "production_readiness": production_readiness,
            "total_contracts": total_contracts,
            "active_contracts": active_contracts,
            "required_gates": len(REQUIRED_GATES),
            "implemented_gates": len(gates & REQUIRED_GATES),
            "errors": len(errors),
        },
        "coverage": {
            "gate_coverage": gate_coverage,
            "runtime_validation_coverage": runtime_coverage,
            "ci_validation_coverage": ci_coverage,
            "valid_example_coverage": valid_example_coverage,
            "invalid_example_coverage": invalid_example_coverage,
            "example_coverage": example_coverage,
        },
        "contracts": contract_rows,
        "registry_rows": registry_rows,
        "breaking_rows": breaking_rows,
        "errors": errors,
        "limitations": [
            "External $ref resolution is not implemented.",
            "The validator covers the governed subset currently used by ReqSys.",
            "Semantic-only changes still require human review.",
        ],
    }


def write_markdown_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    coverage = report["coverage"]
    errors = report["errors"]
    lines = [
        "# Schema Governance Gate",
        "",
        f"Generated at: {report['generated_at']}",
        f"Status: {report['status']}",
        "",
        "## Executive Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Maturity score | {summary['maturity_score']}% |",
        f"| Production readiness | {summary['production_readiness']}% |",
        f"| Risk level | {summary['risk_level']} |",
        f"| Total contracts | {summary['total_contracts']} |",
        f"| Active contracts | {summary['active_contracts']} |",
        f"| Errors | {summary['errors']} |",
        "",
        "## Coverage",
        "",
        "| Coverage | Value |",
        "|---|---:|",
        f"| Gate coverage | {coverage['gate_coverage']}% |",
        f"| Runtime validation | {coverage['runtime_validation_coverage']}% |",
        f"| CI validation | {coverage['ci_validation_coverage']}% |",
        f"| Valid examples | {coverage['valid_example_coverage']}% |",
        f"| Invalid examples | {coverage['invalid_example_coverage']}% |",
        "",
        "## Registry Validation",
        "",
        "| Domain | Schema | Version | Registry Status |",
        "|---|---|---:|---|",
        *report["registry_rows"],
        "",
        "## Breaking Change Detection",
        "",
        "| Contract | Result | Detail |",
        "|---|---|---|",
        *report["breaking_rows"],
        "",
        "## Errors",
    ]
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- None")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def badge_class(value: int) -> str:
    if value >= 90:
        return "ok"
    if value >= 70:
        return "warn"
    return "bad"


def write_json_report(report: dict[str, Any]) -> None:
    REPORT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_html_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    coverage = report["coverage"]
    contracts = report["contracts"]
    errors = report["errors"]
    risk_class = {"low": "ok", "medium": "warn", "high": "bad", "critical": "bad"}.get(summary["risk_level"], "warn")
    contract_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('domain')))}</td>"
        f"<td>{escape(str(item.get('name')))}</td>"
        f"<td>{escape(str(item.get('version')))}</td>"
        f"<td>{escape(str(item.get('schema_path')))}</td>"
        f"<td>{'OK' if item.get('runtime_validation_required') else 'NOK'}</td>"
        f"<td>{'OK' if item.get('ci_validation_required') else 'NOK'}</td>"
        f"<td>{item.get('valid_examples')}</td>"
        f"<td>{item.get('invalid_examples')}</td>"
        "</tr>"
        for item in contracts
    )
    error_items = "".join(f"<li>{escape(error)}</li>" for error in errors) or "<li>None</li>"
    html = f"""<!doctype html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Schema Governance Executive Report</title>
  <style>
    :root {{ --ok:#137333; --warn:#b06000; --bad:#b3261e; --ink:#1f2937; --muted:#6b7280; --bg:#f8fafc; --card:#ffffff; --line:#e5e7eb; }}
    body {{ margin:0; font-family: Arial, Helvetica, sans-serif; background:var(--bg); color:var(--ink); }}
    header {{ padding:24px; background:#111827; color:white; }}
    main {{ padding:24px; max-width:1180px; margin:0 auto; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
    .metric {{ font-size:32px; font-weight:700; margin:8px 0; }}
    .muted {{ color:var(--muted); font-size:13px; }}
    .ok {{ color:var(--ok); }} .warn {{ color:var(--warn); }} .bad {{ color:var(--bad); }}
    .pill {{ display:inline-block; padding:4px 10px; border-radius:999px; font-weight:700; background:#eef2ff; }}
    table {{ width:100%; border-collapse:collapse; background:white; border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
    th, td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; font-size:14px; }}
    th {{ background:#f3f4f6; }}
    section {{ margin-top:24px; }}
    ul {{ background:white; border:1px solid var(--line); border-radius:12px; padding:16px 24px; }}
    @media (max-width:720px) {{ main {{ padding:12px; }} th, td {{ font-size:12px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Schema Governance Executive Report</h1>
    <div>Gerado em {escape(report['generated_at'])} • Status <strong>{escape(report['status'])}</strong></div>
  </header>
  <main>
    <section class=\"grid\">
      <div class=\"card\"><div class=\"muted\">Maturidade</div><div class=\"metric {badge_class(summary['maturity_score'])}\">{summary['maturity_score']}%</div></div>
      <div class=\"card\"><div class=\"muted\">Readiness produção</div><div class=\"metric {badge_class(summary['production_readiness'])}\">{summary['production_readiness']}%</div></div>
      <div class=\"card\"><div class=\"muted\">Risco</div><div class=\"metric {risk_class}\">{escape(summary['risk_level']).upper()}</div></div>
      <div class=\"card\"><div class=\"muted\">Contratos</div><div class=\"metric\">{summary['total_contracts']}</div></div>
    </section>

    <section class=\"grid\">
      <div class=\"card\"><div class=\"muted\">Gate coverage</div><div class=\"metric {badge_class(coverage['gate_coverage'])}\">{coverage['gate_coverage']}%</div></div>
      <div class=\"card\"><div class=\"muted\">Runtime validation</div><div class=\"metric {badge_class(coverage['runtime_validation_coverage'])}\">{coverage['runtime_validation_coverage']}%</div></div>
      <div class=\"card\"><div class=\"muted\">CI validation</div><div class=\"metric {badge_class(coverage['ci_validation_coverage'])}\">{coverage['ci_validation_coverage']}%</div></div>
      <div class=\"card\"><div class=\"muted\">Examples coverage</div><div class=\"metric {badge_class(coverage['example_coverage'])}\">{coverage['example_coverage']}%</div></div>
    </section>

    <section>
      <h2>Contratos governados</h2>
      <table>
        <thead><tr><th>Domínio</th><th>Nome</th><th>Versão</th><th>Schema</th><th>Runtime</th><th>CI</th><th>Valid examples</th><th>Invalid examples</th></tr></thead>
        <tbody>{contract_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Erros e bloqueios</h2>
      <ul>{error_items}</ul>
    </section>
  </main>
</body>
</html>
"""
    REPORT_HTML_PATH.write_text(html, encoding="utf-8")


def write_reports(registry: dict[str, Any], registry_rows: list[str], breaking_rows: list[str], errors: list[str], base_ref: str | None) -> None:
    report = build_executive_report(registry, registry_rows, breaking_rows, errors, base_ref)
    write_markdown_report(report)
    write_json_report(report)
    write_html_report(report)


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
        registry = {"schemas": []}
        errors, registry_rows, breaking_rows = [str(exc)], [], []

    write_reports(registry, registry_rows, breaking_rows, errors, args.base_ref)
    if errors:
        print("Schema governance validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Schema governance validation passed")
    print(f"Reports: {REPORT_PATH.name}, {REPORT_JSON_PATH.name}, {REPORT_HTML_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
