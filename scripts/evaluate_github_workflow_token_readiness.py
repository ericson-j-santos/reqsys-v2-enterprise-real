#!/usr/bin/env python3
"""Build a sanitized readiness decision for the governed GitHub workflow token."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

VALID_STAGES = {
    "missing_secret",
    "authentication_failed",
    "repository_access_failed",
    "workflow_write_failed",
    "cleanup_failed",
    "ready",
}


def evaluate(stage: str, *, probe_branch: str, run_url: str) -> dict[str, object]:
    if stage not in VALID_STAGES:
        raise ValueError("invalid readiness stage")
    ready = stage == "ready"
    return {
        "schema_version": "1.0.0",
        "contract": "github-workflow-token-readiness",
        "decision": "validated" if ready else "blocked",
        "ready": ready,
        "stage": stage,
        "probe_branch": probe_branch,
        "run_url": run_url,
        "secret_value_logged": False,
        "secret_changed": False,
        "promotion_executed": False,
        "production_touched": False,
        "human_action_required": not ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=sorted(VALID_STAGES))
    parser.add_argument("--probe-branch", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    report = evaluate(args.stage, probe_branch=args.probe_branch, run_url=args.run_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"GitHub workflow token readiness: decision={report['decision']} stage={report['stage']}")
    return 1 if args.enforce and not report["ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
