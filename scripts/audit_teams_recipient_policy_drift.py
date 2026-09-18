#!/usr/bin/env python3
"""Audit Teams recipient policies without exposing destination identifiers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

_ALLOWED_SCHEMA_VERSIONS = {"1.0.0", "1.1.0"}
_ALLOWED_DELIVERY_MODES = {"all", "first_success", "channel"}
_ALLOWED_DESTINATION_TYPES = {"auto", "chat", "chat_1a1", "canal", "webhook"}
_ALLOWED_RECIPIENT_SOURCES = {"inline", "runtime_db"}
_ENV_PATTERN = re.compile(
    r"(?mi)^\s*(?:HITL_RECIPIENT_POLICY|TEAMS_RECIPIENT_POLICY)\s*:\s*[\"']?([a-z0-9][a-z0-9_-]*)"
)
_CLI_PATTERN = re.compile(
    r"(?i)--recipient-policy(?:=|\s+)[\"']?([a-z0-9][a-z0-9_-]*)"
)


def _destination_hash(policy: str, destination_type: str, destination_id: str) -> str:
    material = f"{policy}|{destination_type}|{destination_id.casefold()}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("policy configuration must be an object")
    return document


def referenced_policies(workflows_dir: Path) -> dict[str, list[str]]:
    references: dict[str, list[str]] = {}
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted(workflows_dir.glob(pattern)):
            text = path.read_text(encoding="utf-8")
            names = set(_ENV_PATTERN.findall(text)) | set(_CLI_PATTERN.findall(text))
            for name in sorted(names):
                references.setdefault(name.lower(), []).append(path.as_posix())
    return references


def audit(config_path: Path, workflows_dir: Path) -> dict[str, Any]:
    document = load_config(config_path)
    errors: list[str] = []
    warnings: list[str] = []
    policies = document.get("policies")
    if document.get("schema_version") not in _ALLOWED_SCHEMA_VERSIONS:
        errors.append("unsupported_schema_version")
    if not isinstance(policies, list):
        raise ValueError("policies must be a list")

    configured: dict[str, dict[str, Any]] = {}
    inline_destination_count = 0
    for raw_policy in policies:
        if not isinstance(raw_policy, dict):
            errors.append("invalid_policy_object")
            continue
        name = str(raw_policy.get("name") or "").strip().lower()
        if not name:
            errors.append("policy_without_name")
            continue
        if name in configured:
            errors.append(f"duplicate_policy:{name}")
            continue

        delivery_mode = str(raw_policy.get("delivery_mode") or "").strip().lower()
        if delivery_mode not in _ALLOWED_DELIVERY_MODES:
            errors.append(f"invalid_delivery_mode:{name}")

        recipient_source = str(raw_policy.get("recipient_source") or "inline").strip().lower()
        if recipient_source not in _ALLOWED_RECIPIENT_SOURCES:
            errors.append(f"invalid_recipient_source:{name}")
            recipient_source = "inline"

        recipients = raw_policy.get("recipients")
        if not isinstance(recipients, list):
            errors.append(f"recipients_not_list:{name}")
            recipients = []

        if recipient_source == "runtime_db" and recipients:
            errors.append(f"runtime_managed_policy_has_inline_recipients:{name}")

        active_count = 0
        hashes: list[str] = []
        seen: set[tuple[str, str]] = set()
        for recipient in recipients:
            if not isinstance(recipient, dict):
                errors.append(f"invalid_recipient:{name}")
                continue
            destination_id = str(recipient.get("destination_id") or "").strip()
            destination_type = str(recipient.get("destination_type") or "").strip().lower()
            if not destination_id:
                errors.append(f"recipient_without_destination:{name}")
                continue
            if destination_type not in _ALLOWED_DESTINATION_TYPES:
                errors.append(f"invalid_destination_type:{name}")
            key = (destination_type, destination_id.casefold())
            if key in seen:
                errors.append(f"duplicate_destination:{name}")
                continue
            seen.add(key)
            hashes.append(_destination_hash(name, destination_type, destination_id))
            inline_destination_count += 1
            if bool(recipient.get("active", True)):
                active_count += 1

        if recipient_source == "inline" and active_count == 0:
            errors.append(f"policy_without_active_recipients:{name}")
        configured[name] = {
            "delivery_mode": delivery_mode,
            "recipient_source": recipient_source,
            "recipient_count": len(recipients),
            "active_recipient_count": active_count,
            "destination_hashes": sorted(hashes),
        }

    references = referenced_policies(workflows_dir)
    for name in sorted(references):
        if name not in configured:
            errors.append(f"referenced_policy_not_configured:{name}")
    for name in sorted(configured):
        if name not in references:
            warnings.append(f"configured_policy_not_referenced:{name}")

    return {
        "schema_version": "1.1.0",
        "contract": "teams-recipient-policy-drift-audit",
        "result": "pass" if not errors else "fail",
        "summary": {
            "configured_policies": len(configured),
            "referenced_policies": len(references),
            "runtime_managed_policies": sum(
                1 for item in configured.values() if item["recipient_source"] == "runtime_db"
            ),
            "inline_destination_count": inline_destination_count,
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "configured": configured,
        "references": references,
        "errors": errors,
        "warnings": warnings,
        "sensitive_destinations_exposed": inline_destination_count > 0,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Teams recipient-policy drift")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--workflows", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        report = audit(args.config, args.workflows)
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"Teams policy drift audit failed: {type(exc).__name__}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Teams policy drift audit: "
        f"result={report['result']} errors={report['summary']['errors']}"
    )
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
