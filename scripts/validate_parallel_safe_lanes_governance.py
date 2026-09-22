#!/usr/bin/env python3
"""Validate parallel safe lanes governance artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "docs/ops-dashboard/data/parallel-safe-lanes-governance.json"
REQUIRED_LANES = {
    "docs_runbooks_lane",
    "ops_data_lane",
    "validator_scripts_lane",
    "workflow_validation_lane",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "0.1.0":
            fail("schema_version must be 0.1.0")
        lanes = payload.get("safe_lanes") or []
        ids = {lane.get("id") for lane in lanes if isinstance(lane, dict)}
        missing = REQUIRED_LANES - ids
        if missing:
            fail(f"missing lanes: {sorted(missing)}")
        for lane in lanes:
            if not lane.get("allowed_paths") or not lane.get("avoid_paths"):
                fail(f"lane must define allowed_paths and avoid_paths: {lane.get('id')}")
        if not payload.get("conflict_rules"):
            fail("conflict_rules must not be empty")
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "validated": "parallel_safe_lanes_governance"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
