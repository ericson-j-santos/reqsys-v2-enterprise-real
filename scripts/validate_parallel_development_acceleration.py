#!/usr/bin/env python3
"""Validate parallel development acceleration runbook."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK_PATH = ROOT / "docs/runbooks/parallel-development-acceleration.md"
REQUIRED_TERMS = [
    "docs_runbooks_lane",
    "ops_data_lane",
    "validator_scripts_lane",
    "workflow_validation_lane",
    "Runtime/API/Auth",
    "PRs paralelos não devem alterar o mesmo arquivo",
]


def main() -> int:
    try:
        text = RUNBOOK_PATH.read_text(encoding="utf-8")
        missing = [term for term in REQUIRED_TERMS if term not in text]
        if missing:
            raise AssertionError(f"missing terms: {missing}")
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "validated": "parallel_development_acceleration"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
