#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

CARD_ID = "ux-recovery-standard-gold-readiness"


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_metrics(history: list[dict[str, Any]], audits: list[dict[str, Any]] | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    items = [item for item in history if isinstance(item, dict)]
    audit_items = [item for item in (audits or []) if isinstance(item, dict)]
    resolved = [item for item in items if item.get("state") == "resolved"]
    validated = [item for item in resolved if item.get("resolution_signature") and item.get("qualified_resolution_run_id")]
    eligible = [item for item in items if item.get("recommended_due_at")]
    within_sla = 0
    overdue_open = 0
    for item in eligible:
        due = _parse(item.get("recommended_due_at"))
        resolved_at = _parse(item.get("resolved_at"))
        if resolved_at and due and resolved_at <= due:
            within_sla += 1
        elif item.get("state") != "resolved" and due and now > due:
            overdue_open += 1
    mttr: dict[str, float | None] = {}
    for severity in ("high", "medium"):
        values = [float(item["recovery_hours"]) for item in resolved if item.get("severity") == severity and item.get("recovery_hours") is not None]
        mttr[severity] = round(mean(values), 1) if values else None
    reopenings = sum(1 for item in audit_items if item.get("from_state") == "resolved" and item.get("to_state") == "in_progress")
    return {
        "status": "UX_REMEDIATION_GOVERNANCE_MEASURED",
        "total_count": len(items),
        "open_count": sum(1 for item in items if item.get("state") != "resolved"),
        "resolved_count": len(resolved),
        "overdue_open_count": overdue_open,
        "within_sla_percent": round(within_sla / len(eligible) * 100, 1) if eligible else None,
        "validated_closure_rate_percent": round(len(validated) / len(resolved) * 100, 1) if resolved else None,
        "reopening_count": reopenings,
        "mttr_hours_by_severity": mttr,
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
        "generated_at": now.isoformat(),
    }


def consolidate(dashboard: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(dashboard)
    cards = result.get("cards") if isinstance(result.get("cards"), list) else []
    card = next((item for item in cards if isinstance(item, dict) and item.get("id") == CARD_ID), None)
    if card is None:
        raise ValueError(f"card {CARD_ID} não encontrado")
    card["remediation_governance"] = metrics
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--audits", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    history = json.loads(args.history.read_text(encoding="utf-8"))
    audits = json.loads(args.audits.read_text(encoding="utf-8")) if args.audits and args.audits.exists() else []
    output = consolidate(dashboard, build_metrics(history, audits))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
