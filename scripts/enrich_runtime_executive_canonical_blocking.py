#!/usr/bin/env python3
"""Promote temporal blocking to canonical executive contracts.

Reads the regression alert artifact and propagates the canonical fields to:
- docs/ops-dashboard/data/runtime-executive-index.json
- docs/ops-dashboard/data/executive-brief.json

The script is offline/read-only over local artifacts and keeps safe fallbacks
when the regression alert artifact is missing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_ALERT = Path("artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json")
DEFAULT_INDEX = Path("docs/ops-dashboard/data/runtime-executive-index.json")
DEFAULT_BRIEF = Path("docs/ops-dashboard/data/executive-brief.json")
DEFAULT_ALERT_LINK = "artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize_alert(alert: dict[str, Any]) -> dict[str, Any]:
    available = bool(alert)
    status = str(alert.get("status") or "unknown").lower()
    risk = str(alert.get("risk") or "medium").lower()
    violations = alert.get("violations") or []
    production_blocked = bool(alert.get("production_blocked"))
    if not available:
        status = "unknown"
        risk = "medium"
        production_blocked = False
        violations = []
    return {
        "available": available,
        "production_blocked": production_blocked,
        "regression_alert_status": status,
        "regression_alert_risk": risk,
        "regression_alert_violation_count": len(violations),
        "regression_alert_violations": violations,
        "regression_alert_observed": alert.get("observed") or {},
        "regression_alert_thresholds": alert.get("thresholds") or {},
        "source_artifact": DEFAULT_ALERT_LINK if available else "missing",
    }


def enrich_index(index: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any]:
    summary = index.setdefault("summary", {})
    summary["production_blocked"] = canonical["production_blocked"]
    summary["regression_alert_status"] = canonical["regression_alert_status"]
    summary["regression_alert_risk"] = canonical["regression_alert_risk"]
    summary["regression_alert_violation_count"] = canonical["regression_alert_violation_count"]
    if canonical["production_blocked"]:
        summary["status"] = "blocked"
        summary["risk"] = "high"

    cards = index.setdefault("cards", {})
    cards["runtime_executive_regression_alert"] = {
        "available": canonical["available"],
        "status": canonical["regression_alert_status"],
        "risk": canonical["regression_alert_risk"],
        "production_blocked": canonical["production_blocked"],
        "violation_count": canonical["regression_alert_violation_count"],
        "violations": canonical["regression_alert_violations"],
        "observed": canonical["regression_alert_observed"],
        "thresholds": canonical["regression_alert_thresholds"],
        "source_artifact": canonical["source_artifact"],
    }

    links = index.setdefault("links", {})
    links["runtime_executive_regression_alert"] = DEFAULT_ALERT_LINK

    guardrails = index.setdefault("guardrails", [])
    for guardrail in (
        "canonical_temporal_production_blocking_signal",
        "regression_alert_report_only_contract",
        "safe_fallback_when_regression_alert_missing",
    ):
        if guardrail not in guardrails:
            guardrails.append(guardrail)
    return index


def enrich_brief(brief: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any]:
    semaforo = brief.setdefault("semaforo_executivo", {})
    semaforo["bloqueio_temporal"] = "red" if canonical["production_blocked"] else "green" if canonical["available"] else "yellow"
    semaforo["runtime_executive_regression_alert"] = canonical["regression_alert_status"]

    indicadores = brief.setdefault("indicadores_executivos", {})
    indicadores["production_blocked"] = canonical["production_blocked"]
    indicadores["regression_alert_status"] = canonical["regression_alert_status"]
    indicadores["regression_alert_risk"] = canonical["regression_alert_risk"]
    indicadores["regression_alert_violation_count"] = canonical["regression_alert_violation_count"]

    estado = brief.setdefault("estado_unico", {})
    estado["production_blocked"] = canonical["production_blocked"]
    estado["regression_alert_status"] = canonical["regression_alert_status"]
    estado["runtime_executive_regression_alert"] = {
        "available": canonical["available"],
        "status": canonical["regression_alert_status"],
        "risk": canonical["regression_alert_risk"],
        "production_blocked": canonical["production_blocked"],
        "violation_count": canonical["regression_alert_violation_count"],
        "violations": canonical["regression_alert_violations"],
        "observed": canonical["regression_alert_observed"],
        "thresholds": canonical["regression_alert_thresholds"],
        "source_artifact": canonical["source_artifact"],
    }
    if canonical["production_blocked"]:
        estado["pronto_para_producao"] = False

    links = brief.setdefault("links", {})
    links["runtime_executive_regression_alert"] = DEFAULT_ALERT_LINK
    return brief


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote temporal blocking to canonical executive contracts")
    parser.add_argument("--alert", type=Path, default=DEFAULT_ALERT)
    parser.add_argument("--runtime-index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--executive-brief", type=Path, default=DEFAULT_BRIEF)
    args = parser.parse_args()

    canonical = normalize_alert(load_json(args.alert))
    index = load_json(args.runtime_index)
    brief = load_json(args.executive_brief)
    if not index:
        raise SystemExit(f"runtime executive index ausente ou vazio: {args.runtime_index}")
    if not brief:
        raise SystemExit(f"executive brief ausente ou vazio: {args.executive_brief}")

    write_json(args.runtime_index, enrich_index(index, canonical))
    write_json(args.executive_brief, enrich_brief(brief, canonical))
    print(json.dumps({
        "status": "enriched",
        "production_blocked": canonical["production_blocked"],
        "regression_alert_status": canonical["regression_alert_status"],
        "runtime_index": str(args.runtime_index),
        "executive_brief": str(args.executive_brief),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
