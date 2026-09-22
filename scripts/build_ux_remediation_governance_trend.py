#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CARD_ID = "ux-recovery-standard-gold-readiness"
MAX_HISTORY = 30
TARGETS = {
    "within_sla_percent": 90.0,
    "validated_closure_rate_percent": 100.0,
    "reopening_count_max": 0,
    "mttr_high_hours_max": 24.0,
    "mttr_medium_hours_max": 72.0,
}


def _card(dashboard: dict[str, Any]) -> dict[str, Any]:
    cards = dashboard.get("cards") if isinstance(dashboard.get("cards"), list) else []
    for item in cards:
        if isinstance(item, dict) and item.get("id") == CARD_ID:
            return item
    raise ValueError(f"card {CARD_ID} não encontrado")


def evaluate(previous: list[dict[str, Any]] | None, dashboard: dict[str, Any], *, run_id: str, head_sha: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    card = _card(dashboard)
    metrics = card.get("remediation_governance") if isinstance(card.get("remediation_governance"), dict) else {}
    history = [item for item in (previous or []) if isinstance(item, dict)]
    prior = history[-1] if history else None
    mttr = metrics.get("mttr_hours_by_severity") if isinstance(metrics.get("mttr_hours_by_severity"), dict) else {}
    snapshot = {
        "source_run_id": str(run_id),
        "source_head_sha": head_sha,
        "generated_at": metrics.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "within_sla_percent": metrics.get("within_sla_percent"),
        "validated_closure_rate_percent": metrics.get("validated_closure_rate_percent"),
        "reopening_count": int(metrics.get("reopening_count", 0)),
        "overdue_open_count": int(metrics.get("overdue_open_count", 0)),
        "mttr_high_hours": mttr.get("high"),
        "mttr_medium_hours": mttr.get("medium"),
    }
    history = [item for item in history if str(item.get("source_run_id")) != str(run_id)] + [snapshot]
    history = history[-MAX_HISTORY:]

    alerts: list[dict[str, Any]] = []
    def add(code: str, severity: str, message: str, current: Any, target: Any) -> None:
        alerts.append({"code": code, "severity": severity, "message": message, "current": current, "target": target})

    sla = snapshot["within_sla_percent"]
    closure = snapshot["validated_closure_rate_percent"]
    if sla is not None and float(sla) < TARGETS["within_sla_percent"]:
        add("sla_below_target", "high", "percentual dentro do SLA abaixo da meta", sla, TARGETS["within_sla_percent"])
    if closure is not None and float(closure) < TARGETS["validated_closure_rate_percent"]:
        add("validated_closure_below_target", "high", "taxa de fechamento validado abaixo da meta", closure, TARGETS["validated_closure_rate_percent"])
    if snapshot["reopening_count"] > TARGETS["reopening_count_max"]:
        add("reopening_above_target", "medium", "reaberturas acima da meta operacional", snapshot["reopening_count"], TARGETS["reopening_count_max"])
    if snapshot["mttr_high_hours"] is not None and float(snapshot["mttr_high_hours"]) > TARGETS["mttr_high_hours_max"]:
        add("mttr_high_above_target", "high", "MTTR de severidade alta acima do limite", snapshot["mttr_high_hours"], TARGETS["mttr_high_hours_max"])
    if snapshot["mttr_medium_hours"] is not None and float(snapshot["mttr_medium_hours"]) > TARGETS["mttr_medium_hours_max"]:
        add("mttr_medium_above_target", "medium", "MTTR de severidade média acima do limite", snapshot["mttr_medium_hours"], TARGETS["mttr_medium_hours_max"])
    if snapshot["overdue_open_count"] > 0:
        add("overdue_open_items", "high", "existem remediações abertas e vencidas", snapshot["overdue_open_count"], 0)

    deltas: dict[str, Any] = {}
    if prior:
        for key in ("within_sla_percent", "validated_closure_rate_percent", "reopening_count", "mttr_high_hours", "mttr_medium_hours", "overdue_open_count"):
            current = snapshot.get(key)
            before = prior.get(key)
            deltas[key] = None if current is None or before is None else round(float(current) - float(before), 1)
        if deltas.get("within_sla_percent") is not None and deltas["within_sla_percent"] < -5:
            add("sla_deterioration", "high", "SLA deteriorou mais de 5 pontos", deltas["within_sla_percent"], -5)
        if deltas.get("validated_closure_rate_percent") is not None and deltas["validated_closure_rate_percent"] < -5:
            add("validated_closure_deterioration", "high", "fechamento validado deteriorou mais de 5 pontos", deltas["validated_closure_rate_percent"], -5)
        if deltas.get("reopening_count") is not None and deltas["reopening_count"] > 0:
            add("reopening_growth", "medium", "quantidade de reaberturas aumentou", deltas["reopening_count"], 0)

    report = {
        "status": "UX_REMEDIATION_GOVERNANCE_DETERIORATION" if alerts else "UX_REMEDIATION_GOVERNANCE_STABLE",
        "alerts": alerts,
        "alert_count": len(alerts),
        "highest_severity": "high" if any(item["severity"] == "high" for item in alerts) else ("medium" if alerts else "none"),
        "targets": TARGETS,
        "deltas": deltas,
        "latest": snapshot,
        "sample_count": len(history),
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    output = deepcopy(dashboard)
    _card(output)["remediation_governance_trend"] = report
    return history, report, output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--history-output", required=True, type=Path)
    parser.add_argument("--report-output", required=True, type=Path)
    parser.add_argument("--dashboard-output", required=True, type=Path)
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous and args.previous.exists() else []
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    history, report, output = evaluate(previous, dashboard, run_id=args.run_id, head_sha=args.head_sha)
    args.history_output.parent.mkdir(parents=True, exist_ok=True)
    args.history_output.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.dashboard_output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
