#!/usr/bin/env python3
"""Validate Parallel Safe Lanes visual page."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs/ops-dashboard/parallel-safe-lanes.html"
DATA_PATH = ROOT / "docs/ops-dashboard/data/parallel-safe-lanes-governance.json"
REQUIRED_TERMS = [
    "Parallel Safe Lanes",
    "parallel-safe-lanes-governance.json",
    "safe_lanes",
    "conflict_rules",
    "max_parallel_prs_recommended",
]


def main() -> int:
    try:
        html = HTML_PATH.read_text(encoding="utf-8")
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        missing = [term for term in REQUIRED_TERMS if term not in html]
        if missing:
            raise AssertionError(f"missing visual terms: {missing}")
        if not data.get("safe_lanes"):
            raise AssertionError("safe_lanes must not be empty")
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "validated": "parallel_safe_lanes_visual"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
