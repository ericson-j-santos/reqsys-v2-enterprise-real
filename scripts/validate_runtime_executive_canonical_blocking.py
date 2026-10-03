#!/usr/bin/env python3
"""Validate canonical temporal blocking fields in executive contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "ops-dashboard" / "data" / "runtime-executive-index.json"
BRIEF = ROOT / "docs" / "ops-dashboard" / "data" / "executive-brief.json"
ALERT_LINK = "artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json"

REQUIRED_SUMMARY = {
    "production_blocked",
    "regression_alert_status",
    "regression_alert_risk",
    "regression_alert_violation_count",
}


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(f"arquivo ausente: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    index = load(INDEX)
    summary = index.get("summary") or {}
    missing = sorted(REQUIRED_SUMMARY - set(summary))
    if missing:
        raise SystemExit(f"runtime executive summary sem campos canonicos: {missing}")
    card = (index.get("cards") or {}).get("runtime_executive_regression_alert") or {}
    if not card:
        raise SystemExit("runtime executive index sem card runtime_executive_regression_alert")
    if card.get("production_blocked") != summary.get("production_blocked"):
        raise SystemExit("production_blocked divergente entre summary e card")
    if (index.get("links") or {}).get("runtime_executive_regression_alert") != ALERT_LINK:
        raise SystemExit("runtime executive index sem link oficial do regression alert")

    brief = load(BRIEF)
    estado = brief.get("estado_unico") or {}
    indicadores = brief.get("indicadores_executivos") or {}
    semaforo = brief.get("semaforo_executivo") or {}
    for field in ("production_blocked", "regression_alert_status"):
        if field not in estado:
            raise SystemExit(f"executive brief estado_unico sem {field}")
    for field in ("production_blocked", "regression_alert_status", "regression_alert_risk", "regression_alert_violation_count"):
        if field not in indicadores:
            raise SystemExit(f"executive brief indicadores sem {field}")
    if "bloqueio_temporal" not in semaforo:
        raise SystemExit("executive brief sem semaforo_executivo.bloqueio_temporal")
    if (brief.get("links") or {}).get("runtime_executive_regression_alert") != ALERT_LINK:
        raise SystemExit("executive brief sem link oficial do regression alert")

    print("runtime executive canonical blocking validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
