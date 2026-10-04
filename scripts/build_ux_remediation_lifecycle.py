#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

CARD_ID = "ux-recovery-standard-gold-readiness"
SLA_HOURS = {"high": 24, "medium": 72, "none": 0}
OWNER_BY_ALERT = {
    "recovery_rate_drop": "UX_UI",
    "confidence_drop": "OBSERVABILIDADE",
    "recovery_time_increase": "UX_UI",
    "qualified_sequence_break": "QA_GOVERNANCA",
}


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_lifecycle(dashboard: dict[str, Any], previous: list[dict[str, Any]] | None = None, *, now: datetime | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now = now or datetime.now(timezone.utc)
    result = deepcopy(dashboard)
    cards = result.get("cards") if isinstance(result.get("cards"), list) else []
    history = [item for item in (previous or []) if isinstance(item, dict)]
    card = next((item for item in cards if isinstance(item, dict) and item.get("id") == CARD_ID), None)
    if card is None:
        raise ValueError(f"card {CARD_ID} não encontrado")
    regression = card.get("regression") if isinstance(card.get("regression"), dict) else {}
    recommendations = regression.get("recommendations") if isinstance(regression.get("recommendations"), list) else []
    latest = card.get("latest_evidence") if isinstance(card.get("latest_evidence"), dict) else {}
    run_id = str(latest.get("source_run_id") or regression.get("source_run_id") or "unknown")

    active = []
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        severity = str(rec.get("severity", "medium"))
        alert = str(rec.get("alert", "unknown"))
        opened_at = _parse(rec.get("evidence", {}).get("generated_at")) or now
        sla_hours = SLA_HOURS.get(severity, 72)
        due_at = opened_at + timedelta(hours=sla_hours) if sla_hours else opened_at
        active.append({
            "id": f"{run_id}:{alert}",
            "alert": alert,
            "severity": severity,
            "suggested_owner": OWNER_BY_ALERT.get(alert, "UX_UI"),
            "sla_hours": sla_hours,
            "opened_at": opened_at.isoformat(),
            "recommended_due_at": due_at.isoformat(),
            "state": "open",
            "resolution_evidence": None,
            "resolved_at": None,
            "recovery_hours": None,
            "source_run_id": run_id,
            "source_head_sha": rec.get("evidence", {}).get("source_head_sha"),
        })

    existing = {str(item.get("id")): item for item in history if item.get("id")}
    for item in active:
        existing[item["id"]] = {**existing.get(item["id"], {}), **item}
    history = list(existing.values())[-100:]
    resolved_hours = [float(item["recovery_hours"]) for item in history if item.get("state") == "resolved" and item.get("recovery_hours") is not None]
    lifecycle = {
        "status": "UX_REMEDIATION_ACTIVE" if active else "UX_REMEDIATION_CLEAR",
        "open_count": len(active),
        "overdue_count": sum(1 for item in active if _parse(item["recommended_due_at"]) and _parse(item["recommended_due_at"]) < now),
        "items": active,
        "mean_time_to_recovery_hours": round(mean(resolved_hours), 1) if resolved_hours else None,
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
        "generated_at": now.isoformat(),
    }
    card["remediation_lifecycle"] = lifecycle
    return result, history


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--dashboard-output", required=True, type=Path)
    parser.add_argument("--history-output", required=True, type=Path)
    args = parser.parse_args()
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous and args.previous.exists() else []
    output, history = build_lifecycle(dashboard, previous)
    args.dashboard_output.parent.mkdir(parents=True, exist_ok=True)
    args.dashboard_output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.history_output.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
