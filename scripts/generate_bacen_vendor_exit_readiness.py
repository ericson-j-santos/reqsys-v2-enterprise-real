#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REQUIRED_FIELDS = ("portability", "termination_and_deletion")
APPROVED_VALUE = "formally_approved"


def load_manifest(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifesto DPA inválido")
    return payload


def build_report(manifest_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    vendors = manifest.get("vendors") or []
    if not isinstance(vendors, list):
        raise ValueError("vendors deve ser lista")

    ready: list[str] = []
    pending: dict[str, list[str]] = {}
    duplicate_ids: list[str] = []
    seen: set[str] = set()

    for index, vendor in enumerate(vendors):
        if not isinstance(vendor, dict) or not vendor.get("id"):
            raise ValueError(f"fornecedor {index} sem id")
        vendor_id = str(vendor["id"])
        if vendor_id in seen:
            duplicate_ids.append(vendor_id)
        seen.add(vendor_id)
        missing = [field for field in REQUIRED_FIELDS if not vendor.get(field)]
        not_approved = [field for field in REQUIRED_FIELDS if vendor.get(field) != APPROVED_VALUE]
        findings = sorted(set(missing + not_approved))
        if findings:
            pending[vendor_id] = findings
        else:
            ready.append(vendor_id)

    structural_error = bool(duplicate_ids)
    total = len(seen)
    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_vendors": total,
            "exit_ready_vendors": len(ready),
            "pending_vendors": len(pending),
            "coverage_percent": round((len(ready) / total * 100), 2) if total else 0.0,
        },
        "exit_ready_vendor_ids": sorted(ready),
        "pending_requirements": pending,
        "duplicate_vendor_ids": sorted(set(duplicate_ids)),
        "automatic_blocking": structural_error,
        "control_status": "implemented" if total and not pending and not structural_error else "partial",
        "mode": "advisory",
        "production_touched": False,
        "next_stage": "formalize_portability_and_termination_controls",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalia prontidão de saída, portabilidade e exclusão")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
