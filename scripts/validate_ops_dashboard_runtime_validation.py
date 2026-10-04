#!/usr/bin/env python3
"""Validate runtime validation consolidator artifacts consumed by the Ops Dashboard.

Read-only, offline validator for executive-brief.json and runtime-executive-index.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTIVE_BRIEF = ROOT / "docs/ops-dashboard/data/executive-brief.json"
RUNTIME_EXECUTIVE_INDEX = ROOT / "docs/ops-dashboard/data/runtime-executive-index.json"
RUNTIME_VALIDATION_SNAPSHOT = ROOT / "artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json"

REQUIRED_BRIEF_KEYS = {
    "schema_version",
    "generated_at",
    "repository",
    "branch",
    "semaforo_executivo",
    "indicadores_executivos",
    "estado_unico",
    "proximo_incremento_seguro",
    "source_artifact",
}

REQUIRED_SEMAFORO_KEYS = {
    "merge_queue",
    "runtime_publico",
    "risco_operacional",
    "governanca",
}

REQUIRED_EXECUTIVE_LINKS = {
    "executive_brief",
    "runtime_validation_snapshot",
    "runtime_executive_index",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def load_json(path: Path) -> dict:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(payload, dict):
        fail(f"expected object in {path.relative_to(ROOT)}")
    return payload


def validate_executive_brief() -> None:
    payload = load_json(EXECUTIVE_BRIEF)
    missing = REQUIRED_BRIEF_KEYS - set(payload)
    if missing:
        fail(f"executive-brief.json missing keys: {sorted(missing)}")
    semaforo = payload.get("semaforo_executivo") or {}
    missing_semaforo = REQUIRED_SEMAFORO_KEYS - set(semaforo)
    if missing_semaforo:
        fail(f"executive-brief semaforo_executivo missing keys: {sorted(missing_semaforo)}")
    indicators = payload.get("indicadores_executivos") or {}
    if not isinstance(indicators.get("risco_operacional_percent"), int | float):
        fail("executive-brief indicadores_executivos.risco_operacional_percent missing")
    if payload.get("source_artifact") != "runtime-validation-snapshot.json":
        fail("executive-brief source_artifact must reference runtime-validation-snapshot.json")


def validate_runtime_executive_index() -> None:
    payload = load_json(RUNTIME_EXECUTIVE_INDEX)
    links = payload.get("links") or {}
    missing = REQUIRED_EXECUTIVE_LINKS - set(links)
    if missing:
        fail(f"runtime-executive-index.json missing links: {sorted(missing)}")
    if not str(links["executive_brief"]).endswith("executive-brief.json"):
        fail("runtime-executive-index executive_brief link must point to executive-brief.json")
    cards = payload.get("cards") or {}
    if "runtime_validation" not in cards:
        fail("runtime-executive-index cards must include runtime_validation")


def validate_snapshot_when_present() -> None:
    if not RUNTIME_VALIDATION_SNAPSHOT.exists():
        return
    payload = load_json(RUNTIME_VALIDATION_SNAPSHOT)
    for key in ("schema_version", "overall_state", "validation_score", "operational_risk_percent"):
        if key not in payload:
            fail(f"runtime-validation-snapshot missing key: {key}")
    gold = payload.get("gold_standard_operational_risk") or {}
    if not isinstance(gold.get("overall_score"), int | float):
        fail("runtime-validation-snapshot gold_standard_operational_risk.overall_score missing")


def main() -> int:
    try:
        validate_executive_brief()
        validate_runtime_executive_index()
        validate_snapshot_when_present()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "validated": "ops_dashboard_runtime_validation"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
