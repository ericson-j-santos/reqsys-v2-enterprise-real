#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

PENDING_VALUES = {"", "missing", "unknown", "unclassified", "pending"}


def load_register(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("registro de terceiros deve ser um objeto YAML")
    return payload


def build_report(path: Path) -> dict[str, Any]:
    register = load_register(path)
    providers = register.get("providers") or []
    if not isinstance(providers, list):
        raise ValueError("providers deve ser uma lista")

    seen: set[str] = set()
    duplicates: list[str] = []
    invalid_entries: list[str] = []
    pending: list[str] = []
    distribution: Counter[str] = Counter()

    for index, provider in enumerate(providers):
        if not isinstance(provider, dict) or not provider.get("id"):
            invalid_entries.append(str(index))
            continue
        vendor_id = str(provider["id"])
        if vendor_id in seen:
            duplicates.append(vendor_id)
        seen.add(vendor_id)

        classification = str(provider.get("data_classification") or "missing").strip().lower()
        distribution[classification] += 1
        if classification in PENDING_VALUES:
            pending.append(vendor_id)

    blocking = bool(duplicates or invalid_entries)
    complete = bool(providers) and not blocking and not pending
    classified_count = len(providers) - len(pending)
    coverage = round((classified_count / len(providers) * 100), 2) if providers else 0.0

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "source": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "summary": {
            "total_vendors": len(providers),
            "classified_vendors": classified_count,
            "pending_classification": len(pending),
            "coverage_percent": coverage,
        },
        "classification_distribution": dict(sorted(distribution.items())),
        "pending_vendor_ids": sorted(pending),
        "duplicate_vendor_ids": sorted(set(duplicates)),
        "invalid_entries": invalid_entries,
        "classification_complete": complete,
        "control_status": "implemented" if complete else "partial",
        "automatic_blocking": blocking,
        "human_action_required": not complete,
        "production_touched": False,
        "next_stage": "complete_data_classification_for_pending_vendors",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera prontidão de classificação de dados BACEN-05")
    parser.add_argument("--register", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(args.register)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
