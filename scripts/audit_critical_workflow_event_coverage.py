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

DEFAULT_ALIASES = {
    "ci.yml": ("ci.yml", "ci-merge-group-adapter.yml"),
}


def _triggers(path: Path) -> set[str]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    triggers = value.get("on") or value.get(True) or {}
    if isinstance(triggers, str):
        return {triggers}
    if isinstance(triggers, list):
        return set(triggers)
    if isinstance(triggers, dict):
        return set(triggers)
    return set()


def audit(workflow_dir: Path, critical: set[str] | None = None) -> dict[str, Any]:
    critical = critical or DEFAULT_CRITICAL
    rows = []
    for name in sorted(critical):
        candidates = DEFAULT_ALIASES.get(name, (name,)) if critical == DEFAULT_CRITICAL else (name,)
        existing = [candidate for candidate in candidates if (workflow_dir / candidate).exists()]
        trigger_union: set[str] = set()
        for candidate in existing:
            trigger_union.update(_triggers(workflow_dir / candidate))

        has_pr = "pull_request" in trigger_union
        has_merge_group = "merge_group" in trigger_union
        gap_reason = None
        if not existing:
            gap_reason = "WORKFLOW_NOT_FOUND"
        elif not has_pr and not has_merge_group:
            gap_reason = "PULL_REQUEST_AND_MERGE_GROUP_MISSING"
        elif not has_pr:
            gap_reason = "PULL_REQUEST_MISSING"
        elif not has_merge_group:
            gap_reason = "MERGE_GROUP_MISSING"

        rows.append({
            "workflow": name,
            "exists": bool(existing),
            "pull_request": has_pr,
            "merge_group": has_merge_group,
            "coverage_sources": existing,
            "coverage_mode": "logical_adapter" if len(existing) > 1 else "direct",
            "gap_reason": gap_reason,
        })

    complete = [row for row in rows if row["exists"] and row["pull_request"] and row["merge_group"]]
    gaps = [row for row in rows if row not in complete]
    coverage_percent = round((len(complete) / len(rows)) * 100, 2) if rows else 100
    return {
        "schema_version": "1.2.0",
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
