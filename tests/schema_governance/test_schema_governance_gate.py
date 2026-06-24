#!/usr/bin/env python3
"""Self-validation tests for the ReqSys Schema Governance Gate.

The tests use only Python standard library modules and validate the core
breaking-change rules without depending on GitHub Actions internals.
"""

from __future__ import annotations

import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.schema_governance.validate_schema_governance import (  # noqa: E402
    detect_breaking_changes,
    is_major_bump,
    parse_semver,
    validate_schema_document,
)


def base_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://reqsys.local/schemas/test-contract.schema.json",
        "title": "Test Contract",
        "type": "object",
        "required": ["schema_version", "id", "status"],
        "properties": {
            "schema_version": {"type": "string", "const": "1.0.0"},
            "id": {"type": "string"},
            "status": {"type": "string", "enum": ["draft", "approved", "rejected"]},
            "score": {"type": "number", "minimum": 0, "maximum": 100},
            "metadata": {
                "type": "object",
                "required": ["source"],
                "properties": {
                    "source": {"type": "string"},
                    "channel": {"type": "string", "enum": ["api", "ui"]},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


def with_version(schema: dict, version: str) -> dict:
    cloned = copy.deepcopy(schema)
    cloned["properties"]["schema_version"]["const"] = version
    return cloned


def assert_has_change(changes: list[str], expected_fragment: str) -> None:
    assert any(expected_fragment in change for change in changes), changes


def test_semver_parsing_and_major_bump() -> None:
    assert parse_semver("1.2.3") == (1, 2, 3)
    assert parse_semver("1.2") is None
    assert is_major_bump("1.0.0", "2.0.0") is True
    assert is_major_bump("1.0.0", "1.1.0") is False
    assert is_major_bump("1.0.0", "1.0.1") is False


def test_compatible_optional_field_is_allowed() -> None:
    old = base_schema()
    new = with_version(old, "1.1.0")
    new["properties"]["optional_note"] = {"type": "string"}

    changes = detect_breaking_changes(old, new, "schemas/test.schema.json")

    assert changes == []


def test_required_field_added_is_breaking() -> None:
    old = base_schema()
    new = copy.deepcopy(old)
    new["properties"]["owner"] = {"type": "string"}
    new["required"].append("owner")

    changes = detect_breaking_changes(old, new, "schemas/test.schema.json")

    assert_has_change(changes, "required property added")


def test_property_removed_is_breaking() -> None:
    old = base_schema()
    new = copy.deepcopy(old)
    del new["properties"]["score"]

    changes = detect_breaking_changes(old, new, "schemas/test.schema.json")

    assert_has_change(changes, "property removed")


def test_type_changed_is_breaking() -> None:
    old = base_schema()
    new = copy.deepcopy(old)
    new["properties"]["score"]["type"] = "string"

    changes = detect_breaking_changes(old, new, "schemas/test.schema.json")

    assert_has_change(changes, "type changed")


def test_enum_value_removed_is_breaking() -> None:
    old = base_schema()
    new = copy.deepcopy(old)
    new["properties"]["status"]["enum"] = ["draft", "approved"]

    changes = detect_breaking_changes(old, new, "schemas/test.schema.json")

    assert_has_change(changes, "enum values removed")


def test_additional_properties_relaxed_is_breaking() -> None:
    old = base_schema()
    new = copy.deepcopy(old)
    new["properties"]["metadata"]["additionalProperties"] = True

    changes = detect_breaking_changes(old, new, "schemas/test.schema.json")

    assert_has_change(changes, "additionalProperties was relaxed")


def test_major_bump_allows_breaking_change_policy() -> None:
    old = base_schema()
    new = with_version(old, "2.0.0")
    del new["properties"]["score"]

    changes = detect_breaking_changes(old, new, "schemas/test.schema.json")

    assert changes
    assert is_major_bump("1.0.0", "2.0.0") is True


def test_schema_document_requires_semver_schema_version() -> None:
    schema = with_version(base_schema(), "v1")

    errors = validate_schema_document(schema, ROOT / "schemas" / "test.schema.json")

    assert_has_change(errors, "schema_version const must be SemVer")


def run() -> int:
    tests = [
        test_semver_parsing_and_major_bump,
        test_compatible_optional_field_is_allowed,
        test_required_field_added_is_breaking,
        test_property_removed_is_breaking,
        test_type_changed_is_breaking,
        test_enum_value_removed_is_breaking,
        test_additional_properties_relaxed_is_breaking,
        test_major_bump_allows_breaking_change_policy,
        test_schema_document_requires_semver_schema_version,
    ]
    failures: list[str] = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:  # pragma: no cover - explicit CI diagnostics
            failures.append(f"{test.__name__}: {exc}")
            print(f"FAIL {test.__name__}: {exc}", file=sys.stderr)

    if failures:
        print("Schema governance self-validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Schema governance self-validation passed: {len(tests)} tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
