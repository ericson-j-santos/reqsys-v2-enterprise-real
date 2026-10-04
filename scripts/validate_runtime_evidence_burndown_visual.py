#!/usr/bin/env python3
"""Validate Runtime Evidence Burndown visual page."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs/ops-dashboard/runtime-evidence-burndown.html"
DATA_PATH = ROOT / "docs/ops-dashboard/data/runtime-evidence-burndown.json"
REQUIRED_TERMS = [
    "Runtime Evidence Burndown",
    "runtime-evidence-burndown.json",
    "dimensions",
    "history",
    "remaining_gap",
]


def main() -> int:
    try:
        html = HTML_PATH.read_text(encoding="utf-8")
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        missing = [term for term in REQUIRED_TERMS if term not in html]
        if missing:
            raise AssertionError(f"missing visual terms: {missing}")
        if not data.get("dimensions"):
            raise AssertionError("dimensions must not be empty")
        if not data.get("history"):
            raise AssertionError("history must not be empty")
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "validated": "runtime_evidence_burndown_visual"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
