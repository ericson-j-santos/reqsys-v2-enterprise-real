#!/usr/bin/env python3
"""Validate runtime evidence burndown seed artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "docs/ops-dashboard/data/runtime-evidence-burndown.json"
REQUIRED_DIMENSIONS = {
    "ci_cd_stability",
    "runtime_governance",
    "evidence_consolidation",
    "observability_traceability",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "0.1.0":
            fail("schema_version must be 0.1.0")
        overall = payload.get("overall") or {}
        if overall.get("current_score", 0) > overall.get("target_score", 100):
            fail("current_score must not exceed target_score")
        dimensions = payload.get("dimensions") or []
        ids = {item.get("id") for item in dimensions if isinstance(item, dict)}
        missing = REQUIRED_DIMENSIONS - ids
        if missing:
            fail(f"missing dimensions: {sorted(missing)}")
        for item in dimensions:
            current = item.get("current_percent")
            target = item.get("target_percent")
            gap = item.get("gap_percent")
            if current is None or target is None or gap is None:
                fail(f"dimension missing numeric fields: {item.get('id')}")
            if current + gap != target:
                fail(f"dimension gap mismatch: {item.get('id')}")
        if not payload.get("history"):
            fail("history must not be empty")
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "validated": "runtime_evidence_burndown"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
