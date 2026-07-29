#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

APPROVED = "formally_approved"


def build_report(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("vendors"), list):
        raise ValueError("manifesto DPA inválido")
    seen: set[str] = set()
    approved: list[str] = []
    pending: list[str] = []
    errors: list[str] = []
    for item in payload["vendors"]:
        if not isinstance(item, dict) or not item.get("id"):
            errors.append("vendor_without_id")
            continue
        vendor_id = str(item["id"])
        if vendor_id in seen:
            errors.append(f"duplicate_vendor:{vendor_id}")
        seen.add(vendor_id)
        if item.get("subprocessors") == APPROVED:
            approved.append(vendor_id)
        else:
            pending.append(vendor_id)
    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "summary": {"vendors": len(seen), "approved": len(approved), "pending": len(pending)},
        "approved_vendor_ids": sorted(approved),
        "pending_vendor_ids": sorted(pending),
        "control_status": "implemented" if seen and not pending and not errors else "partial",
        "automatic_blocking": bool(errors),
        "errors": sorted(errors),
        "human_action_required": bool(pending),
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
