#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CRITICAL = {
    "ci.yml",
    "ci-enterprise-fast.yml",
    "pr-evidence-gate.yml",
    "governed-merge-queue.yml",
    "security-baseline-gate.yml",
}


def audit(workflow_dir: Path, critical: set[str] | None = None) -> dict[str, Any]:
    critical = critical or DEFAULT_CRITICAL
    rows = []
    for name in sorted(critical):
        path = workflow_dir / name
        if not path.exists():
            rows.append({
                "workflow": name,
                "exists": False,
                "pull_request": False,
                "merge_group": False,
                "gap_reason": "WORKFLOW_NOT_FOUND",
            })
            continue
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        triggers = value.get("on") or value.get(True) or {}
        if isinstance(triggers, str):
            trigger_names = {triggers}
        elif isinstance(triggers, list):
            trigger_names = set(triggers)
        elif isinstance(triggers, dict):
            trigger_names = set(triggers)
        else:
            trigger_names = set()
        has_pr = "pull_request" in trigger_names
        has_merge_group = "merge_group" in trigger_names
        gap_reason = None
        if not has_pr and not has_merge_group:
            gap_reason = "PULL_REQUEST_AND_MERGE_GROUP_MISSING"
        elif not has_pr:
            gap_reason = "PULL_REQUEST_MISSING"
        elif not has_merge_group:
            gap_reason = "MERGE_GROUP_MISSING"
        rows.append({
            "workflow": name,
            "exists": True,
            "pull_request": has_pr,
            "merge_group": has_merge_group,
            "gap_reason": gap_reason,
        })

    complete = [r for r in rows if r["exists"] and r["pull_request"] and r["merge_group"]]
    gaps = [r for r in rows if r not in complete]
    coverage_percent = round((len(complete) / len(rows)) * 100, 2) if rows else 100
    return {
        "schema_version": "1.1.0",
        "contract": "reqsys-critical-workflow-event-coverage",
        "status": "COVERAGE_COMPLETE" if not gaps else "COVERAGE_GAPS_FOUND",
        "critical_workflow_count": len(rows),
        "complete_workflow_count": len(complete),
        "coverage_percent": coverage_percent,
        "risk": "low" if not gaps else "high",
        "workflows": rows,
        "gaps": gaps,
        "throughput_increase_allowed": not gaps,
        "parallelism_decision": "INCREASE_ALLOWED" if not gaps else "KEEP_CURRENT_LIMITS",
        "human_approval_required": True,
        "promotion_allowed": False,
        "mode": "advisory",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-dir", default=".github/workflows", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.workflow_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "coverage_percent": result["coverage_percent"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())