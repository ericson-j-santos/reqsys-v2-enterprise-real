#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

APPROVED_STATUSES = {"approved", "signed", "complete", "validated", "formally_approved"}
HIGH_CRITICALITY = {"high", "critical"}


def load_register(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("registro de terceiros deve ser um objeto YAML")
    return payload


def build_report(register_path: Path) -> dict[str, Any]:
    register = load_register(register_path)
    providers = register.get("providers") or []
    if not isinstance(providers, list):
        raise ValueError("providers deve ser uma lista")

    provider_ids: set[str] = set()
    duplicate_provider_ids: list[str] = []
    structurally_invalid: list[str] = []
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "provider_count": 0,
            "high_or_critical_count": 0,
            "pending_risk_review_count": 0,
            "pending_dpa_count": 0,
            "provider_ids": [],
        }
    )

    for index, provider in enumerate(providers):
        if not isinstance(provider, dict):
            structurally_invalid.append(f"index:{index}")
            continue
        provider_id = str(provider.get("id") or f"index:{index}")
        classification = str(provider.get("data_classification") or "").strip()
        criticality = str(provider.get("criticality") or "").lower()
        if provider_id in provider_ids:
            duplicate_provider_ids.append(provider_id)
        provider_ids.add(provider_id)
        if not classification or not criticality:
            structurally_invalid.append(provider_id)
            continue

        bucket = grouped[classification]
        bucket["provider_count"] += 1
        bucket["provider_ids"].append(provider_id)
        if criticality in HIGH_CRITICALITY:
            bucket["high_or_critical_count"] += 1
        risk_status = str(provider.get("risk_review_status") or "missing").lower()
        dpa_status = str(provider.get("dpa_status") or "missing").lower()
        if risk_status not in APPROVED_STATUSES:
            bucket["pending_risk_review_count"] += 1
        if dpa_status not in APPROVED_STATUSES:
            bucket["pending_dpa_count"] += 1

    classifications = {
        key: {**value, "provider_ids": sorted(value["provider_ids"])}
        for key, value in sorted(grouped.items())
    }
    pending_risk = sum(item["pending_risk_review_count"] for item in classifications.values())
    pending_dpa = sum(item["pending_dpa_count"] for item in classifications.values())
    structural_errors = bool(duplicate_provider_ids or structurally_invalid)
    fully_approved = bool(providers) and not structural_errors and not pending_risk and not pending_dpa

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "source_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "summary": {
            "provider_count": len(providers),
            "classification_count": len(classifications),
            "high_or_critical_provider_count": sum(
                item["high_or_critical_count"] for item in classifications.values()
            ),
            "pending_risk_review_count": pending_risk,
            "pending_dpa_count": pending_dpa,
        },
        "classifications": classifications,
        "duplicate_provider_ids": sorted(set(duplicate_provider_ids)),
        "structurally_invalid_provider_ids": sorted(structurally_invalid),
        "automatic_blocking": structural_errors,
        "control_status": "implemented" if fully_approved else "partial",
        "human_action_required": not fully_approved,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = build_report(args.register)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
