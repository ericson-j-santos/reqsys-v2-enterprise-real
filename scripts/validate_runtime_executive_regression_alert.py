#!/usr/bin/env python3
"""Validate Runtime Executive temporal regression alert contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts" / "runtime-executive-regression-alert" / "runtime-executive-regression-alert.json"
BRIEF = ROOT / "docs" / "ops-dashboard" / "data" / "executive-brief.json"

REQUIRED = {
    "schema_version",
    "contract",
    "status",
    "production_blocked",
    "risk",
    "violations",
    "guardrails",
}


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(f"arquivo ausente: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    report = load(REPORT)
    missing = sorted(REQUIRED - set(report))
    if missing:
        raise SystemExit(f"regression alert sem campos obrigatorios: {missing}")
    if report.get("contract") != "runtime-executive-regression-alert":
        raise SystemExit("contract invalido no regression alert")
    if report.get("status") not in {"passed", "warning", "blocked"}:
        raise SystemExit("status invalido no regression alert")
    if report.get("risk") not in {"low", "medium", "high"}:
        raise SystemExit("risk invalido no regression alert")
    brief = load(BRIEF)
    estado = brief.get("estado_unico") or {}
    if "runtime_executive_regression_alert" not in estado:
        raise SystemExit("executive brief sem runtime_executive_regression_alert")
    links = brief.get("links") or {}
    if links.get("runtime_executive_regression_alert") != "artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json":
        raise SystemExit("executive brief sem link oficial do regression alert")
    print("runtime executive regression alert validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
