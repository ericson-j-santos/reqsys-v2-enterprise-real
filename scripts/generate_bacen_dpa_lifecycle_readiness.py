#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


def load_contract(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("contrato DPA inválido")
    return payload


def parse_date(value: Any, field: str, vendor_id: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{vendor_id}: {field} deve usar YYYY-MM-DD") from exc


def build_report(contract_path: Path, reference_date: date, warning_days: int) -> dict[str, Any]:
    contract = load_contract(contract_path)
    records = contract.get("records") or []
    if not isinstance(records, list):
        raise ValueError("records deve ser lista")

    expired: list[str] = []
    expiring: list[str] = []
    valid: list[str] = []
    pending: list[str] = []

    threshold = reference_date + timedelta(days=warning_days)
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"registro {index} inválido")
        vendor_id = str(record.get("vendor_id") or f"index-{index}")
        if record.get("evidence_status") != "validated":
            pending.append(vendor_id)
            continue
        effective_at = parse_date(record.get("effective_at"), "effective_at", vendor_id)
        expires_at = parse_date(record.get("expires_at"), "expires_at", vendor_id)
        if expires_at < effective_at:
            raise ValueError(f"{vendor_id}: expires_at anterior a effective_at")
        if expires_at < reference_date:
            expired.append(vendor_id)
        elif expires_at <= threshold:
            expiring.append(vendor_id)
        else:
            valid.append(vendor_id)

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "reference_date": reference_date.isoformat(),
        "warning_days": warning_days,
        "summary": {
            "total_records": len(records),
            "validated_records": len(expired) + len(expiring) + len(valid),
            "valid_records": len(valid),
            "expiring_records": len(expiring),
            "expired_records": len(expired),
            "pending_records": len(pending),
        },
        "expired_vendor_ids": sorted(expired),
        "expiring_vendor_ids": sorted(expiring),
        "pending_vendor_ids": sorted(pending),
        "automatic_blocking": bool(expired),
        "mode": "advisory" if not expired else "blocking",
        "production_touched": False,
        "next_stage": "renew_expiring_or_expired_dpa_evidence",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalia validade e renovação de evidências DPA")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-date", default=date.today().isoformat())
    parser.add_argument("--warning-days", type=int, default=90)
    args = parser.parse_args()

    if args.warning_days < 1:
        raise ValueError("warning-days deve ser maior que zero")
    report = build_report(args.contract, date.fromisoformat(args.reference_date), args.warning_days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
