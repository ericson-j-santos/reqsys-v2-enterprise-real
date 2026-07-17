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
    "security-baseline.yml",
}


def audit(workflow_dir: Path, critical: set[str] | None = None) -> dict[str, Any]:
    critical = critical or DEFAULT_CRITICAL
    rows = []
    for name in sorted(critical):
        path = workflow_dir / name
        if not path.exists():
            rows.append({"workflow": name, "exists": False, "pull_request": False, "merge_group": False})
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
        rows.append({
            "workflow": name,
            "exists": True,
            "pull_request": "pull_request" in trigger_names,
            "merge_group": "merge_group" in trigger_names,
        })

    complete = [r for r in rows if r["exists"] and r["pull_request"] and r["merge_group"]]
    gaps = [r for r in rows if r not in complete]
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-critical-workflow-event-coverage",
        "status": "COVERAGE_COMPLETE" if not gaps else "COVERAGE_GAPS_FOUND",
        "critical_workflow_count": len(rows),
        "complete_workflow_count": len(complete),
        "coverage_percent": round((len(complete) / len(rows)) * 100, 2) if rows else 100,
        "workflows": rows,
        "gaps": gaps,
        "throughput_increase_allowed": not gaps,
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
