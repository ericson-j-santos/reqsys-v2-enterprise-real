#!/usr/bin/env python3
"""Validate ReqSys Product Intelligence events.

The validator intentionally uses only Python standard library features so it can
run in CI without adding dependencies or changing the product runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "product-intelligence" / "product-intelligence-event.schema.json"
DEFAULT_EVENT_PATH = ROOT / "examples" / "product-intelligence" / "product-intelligence-event.example.json"

REQUIRED_TOP_LEVEL = {
    "schema_version",
    "event_id",
    "event_type",
    "event_class",
    "occurred_at",
    "source",
    "requirement",
    "quality",
    "traceability",
    "governance",
}

VALID_EVENT_TYPES = {
    "requirement.created",
    "requirement.refined",
    "requirement.approved",
    "requirement.rejected",
    "bdd.generated",
    "risk.identified",
    "traceability.linked",
    "decision.recorded",
    "quality.scored",
    "gap.detected",
}

VALID_CHANNELS = {"ui", "api", "agent", "import", "workflow"}
VALID_ACTOR_TYPES = {"user", "agent", "system"}
VALID_REQUIREMENT_TYPES = {"functional", "non_functional", "business_rule", "constraint"}
VALID_REQUIREMENT_STATUSES = {"draft", "refined", "approved", "implemented", "tested", "validated"}
VALID_PRIORITIES = {"must", "should", "could", "wont"}
VALID_CONFIDENCE = {"low", "medium", "high"}
VALID_EVIDENCE_LEVELS = {"none", "partial", "complete"}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"file not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"json root must be an object: {path}")
    return value


def require_object(value: dict[str, Any], key: str) -> dict[str, Any]:
    nested = value.get(key)
    if not isinstance(nested, dict):
        raise ValueError(f"{key} must be an object")
    return nested


def require_array(value: dict[str, Any], key: str) -> list[Any]:
    nested = value.get(key)
    if not isinstance(nested, list):
        raise ValueError(f"{key} must be an array")
    return nested


def require_string(value: dict[str, Any], key: str) -> str:
    nested = value.get(key)
    if not isinstance(nested, str) or not nested.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return nested


def require_boolean(value: dict[str, Any], key: str) -> bool:
    nested = value.get(key)
    if not isinstance(nested, bool):
        raise ValueError(f"{key} must be a boolean")
    return nested


def require_score(value: dict[str, Any], key: str) -> float:
    nested = value.get(key)
    if not isinstance(nested, (int, float)) or isinstance(nested, bool):
        raise ValueError(f"{key} must be a number")
    if nested < 0 or nested > 100:
        raise ValueError(f"{key} must be between 0 and 100")
    return float(nested)


def require_enum(value: dict[str, Any], key: str, allowed: set[str]) -> str:
    nested = require_string(value, key)
    if nested not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"{key} must be one of: {allowed_values}")
    return nested


def validate_event(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def check(fn: Any) -> None:
        try:
            fn()
        except ValueError as exc:
            errors.append(str(exc))

    missing = REQUIRED_TOP_LEVEL - set(event)
    if missing:
        errors.append(f"missing required top-level fields: {', '.join(sorted(missing))}")

    check(lambda: require_enum(event, "schema_version", {"1.0.0"}))
    check(lambda: require_string(event, "event_id"))
    check(lambda: require_enum(event, "event_type", VALID_EVENT_TYPES))
    check(lambda: require_enum(event, "event_class", {"PRODUCT_INTELLIGENCE"}))
    check(lambda: require_string(event, "occurred_at"))

    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    check(lambda: require_object(event, "source"))
    check(lambda: require_string(source, "system"))
    check(lambda: require_enum(source, "channel", VALID_CHANNELS))
    check(lambda: require_enum(source, "actor_type", VALID_ACTOR_TYPES))
    check(lambda: require_string(source, "actor_id"))

    requirement = event.get("requirement") if isinstance(event.get("requirement"), dict) else {}
    check(lambda: require_object(event, "requirement"))
    check(lambda: require_string(requirement, "id"))
    check(lambda: require_string(requirement, "title"))
    check(lambda: require_enum(requirement, "type", VALID_REQUIREMENT_TYPES))
    check(lambda: require_enum(requirement, "status", VALID_REQUIREMENT_STATUSES))
    check(lambda: require_enum(requirement, "priority", VALID_PRIORITIES))
    check(lambda: require_enum(requirement, "confidence", VALID_CONFIDENCE))

    quality = event.get("quality") if isinstance(event.get("quality"), dict) else {}
    check(lambda: require_object(event, "quality"))
    for key in ["bdd_coverage", "ambiguity_score", "traceability_score", "risk_score", "readiness_score"]:
        check(lambda key=key: require_score(quality, key))

    traceability = event.get("traceability") if isinstance(event.get("traceability"), dict) else {}
    check(lambda: require_object(event, "traceability"))
    for key in ["parent_ids", "linked_prs", "linked_tests", "linked_decisions", "linked_risks"]:
        check(lambda key=key: require_array(traceability, key))

    governance = event.get("governance") if isinstance(event.get("governance"), dict) else {}
    check(lambda: require_object(event, "governance"))
    check(lambda: require_string(governance, "correlation_id"))
    check(lambda: require_boolean(governance, "pii_masked"))
    check(lambda: require_boolean(governance, "human_review_required"))
    check(lambda: require_boolean(governance, "ai_generated"))
    check(lambda: require_enum(governance, "evidence_level", VALID_EVIDENCE_LEVELS))

    return errors


def main(argv: list[str]) -> int:
    event_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_EVENT_PATH
    try:
        # Load schema to ensure the versioned contract exists and is valid JSON.
        load_json(SCHEMA_PATH)
        event = load_json(event_path)
        errors = validate_event(event)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("Product Intelligence event validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Product Intelligence event is valid: {event_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
