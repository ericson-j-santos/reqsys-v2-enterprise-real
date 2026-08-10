#!/usr/bin/env python3
"""Evaluate whether critical PR workflows are complete for the current head SHA."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def latest_runs_by_name(runs: list[dict[str, Any]], head_sha: str) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        if str(run.get("head_sha") or "") != head_sha:
            continue
        if str(run.get("event") or "") != "pull_request":
            continue
        name = str(run.get("name") or "").strip()
        if not name:
            continue
        current = selected.get(name)
        candidate_key = (
            int(run.get("run_attempt") or 0),
            str(run.get("created_at") or ""),
            int(run.get("id") or 0),
        )
        current_key = (
            int(current.get("run_attempt") or 0),
            str(current.get("created_at") or ""),
            int(current.get("id") or 0),
        ) if current else (-1, "", -1)
        if current is None or candidate_key > current_key:
            selected[name] = run
    return selected


def evaluate_stability(
    *,
    runs_payload: dict[str, Any],
    policy: dict[str, Any],
    evaluated_sha: str,
    current_sha: str,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    required = policy.get("required_workflows") or []
    allowed = set(policy.get("allowed_conclusions") or ["success", "neutral", "skipped"])
    optional_when_not_registered = set(policy.get("optional_when_not_registered") or [])
    if not isinstance(required, list) or not required or not all(isinstance(item, str) and item.strip() for item in required):
        raise ValueError("policy required_workflows must be a non-empty string list")
    if not allowed:
        raise ValueError("policy allowed_conclusions must not be empty")
    unknown_optional = optional_when_not_registered.difference(required)
    if unknown_optional:
        raise ValueError("policy optional_when_not_registered must be a subset of required_workflows")

    runs = runs_payload.get("workflow_runs") or []
    if not isinstance(runs, list):
        raise ValueError("workflow_runs must be a list")
    latest = latest_runs_by_name(runs, evaluated_sha)

    missing: list[str] = []
    incomplete: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    observed: list[dict[str, Any]] = []
    for workflow in required:
        run = latest.get(workflow)
        if run is None:
            missing.append(workflow)
            observed.append({"workflow": workflow, "status": "missing", "conclusion": "missing"})
            continue
        status = str(run.get("status") or "")
        conclusion = str(run.get("conclusion") or "")
        item = {
            "workflow": workflow,
            "status": status,
            "conclusion": conclusion,
            "run_id": int(run.get("id") or 0),
            "url": str(run.get("html_url") or ""),
        }
        observed.append(item)
        if status != "completed":
            incomplete.append({"workflow": workflow, "status": status})
        elif conclusion not in allowed:
            failed.append({"workflow": workflow, "conclusion": conclusion})

    blocking_missing = [workflow for workflow in missing if workflow not in optional_when_not_registered]
    tolerated_missing = [workflow for workflow in missing if workflow in optional_when_not_registered]
    same_sha = bool(evaluated_sha) and evaluated_sha == current_sha
    stable = same_sha and not blocking_missing and not incomplete and not failed
    if not same_sha:
        decision = "head_sha_changed"
    elif blocking_missing:
        decision = "required_workflows_not_registered"
    elif incomplete:
        decision = "required_workflows_incomplete"
    elif failed:
        decision = "required_workflows_failed"
    else:
        decision = "stable"

    timestamp = observed_at or datetime.now(UTC)
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-current-sha-workflow-stability",
        "observed_at": timestamp.astimezone(UTC).isoformat(),
        "evaluated_sha": evaluated_sha,
        "current_sha": current_sha,
        "same_sha": same_sha,
        "stable": stable,
        "decision": decision,
        "required_workflows": required,
        "allowed_conclusions": sorted(allowed),
        "missing_workflows": blocking_missing,
        "tolerated_missing_workflows": tolerated_missing,
        "optional_when_not_registered": sorted(optional_when_not_registered),
        "incomplete_workflows": incomplete,
        "failed_workflows": failed,
        "observed_workflows": observed,
        "absence_is_success": bool(tolerated_missing) and not blocking_missing,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--evaluated-sha", required=True)
    parser.add_argument("--current-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = evaluate_stability(
        runs_payload=load_object(args.runs),
        policy=load_object(args.policy),
        evaluated_sha=args.evaluated_sha,
        current_sha=args.current_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["stable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
