#!/usr/bin/env python3
"""Valida e resume a matriz Pareto de fechamento de gaps enterprise do ReqSys."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_MATRIX = "docs/padrao-ouro/enterprise-gap-closure-matrix.json"
REQUIRED_PRIORITIES = {"P0", "P1", "P2"}
REQUIRED_FIELDS = {"id", "priority", "pillar", "current_maturity_percent", "target_maturity_percent", "gap", "minimum_increment", "acceptance_evidence", "owners", "rollback"}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(matrix: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    gaps = matrix.get("gaps")
    if not isinstance(gaps, list) or not gaps:
        return ["matrix.gaps must be a non-empty list"]

    seen: set[str] = set()
    priorities: set[str] = set()
    for index, gap in enumerate(gaps, start=1):
        missing = sorted(REQUIRED_FIELDS - set(gap))
        if missing:
            errors.append(f"gap[{index}] missing fields: {', '.join(missing)}")
            continue
        gap_id = str(gap["id"])
        if gap_id in seen:
            errors.append(f"duplicate gap id: {gap_id}")
        seen.add(gap_id)
        priorities.add(str(gap["priority"]))
        if int(gap["target_maturity_percent"]) <= int(gap["current_maturity_percent"]):
            errors.append(f"{gap_id} target_maturity_percent must be greater than current_maturity_percent")
        for list_field in ("acceptance_evidence", "owners"):
            if not isinstance(gap[list_field], list) or not gap[list_field]:
                errors.append(f"{gap_id} {list_field} must be a non-empty list")
        if not str(gap["rollback"]).strip():
            errors.append(f"{gap_id} rollback must not be empty")

    missing_priorities = sorted(REQUIRED_PRIORITIES - priorities)
    if missing_priorities:
        errors.append("missing required priorities: " + ", ".join(missing_priorities))
    return errors


def summary(matrix: dict[str, Any]) -> dict[str, Any]:
    gaps = matrix["gaps"]
    by_priority: dict[str, int] = {}
    for gap in gaps:
        by_priority[gap["priority"]] = by_priority.get(gap["priority"], 0) + 1
    return {
        "schema_version": matrix.get("schema_version"),
        "reference_date": matrix.get("reference_date"),
        "gap_count": len(gaps),
        "by_priority": dict(sorted(by_priority.items())),
        "top_pareto": [gap["id"] for gap in gaps if gap["priority"] in {"P0", "P1"}],
        "target_state": matrix.get("target_state", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ReqSys enterprise gap closure matrix")
    parser.add_argument("--matrix", default=DEFAULT_MATRIX)
    parser.add_argument("--summary-json", default="")
    args = parser.parse_args()

    matrix = load(Path(args.matrix))
    errors = validate(matrix)
    result = {"valid": not errors, "errors": errors, "summary": summary(matrix) if not errors else {}}
    if args.summary_json:
        Path(args.summary_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_json).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
