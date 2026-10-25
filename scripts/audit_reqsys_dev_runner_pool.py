#!/usr/bin/env python3
"""Build sanitized evidence from portable ReqSys DEV runner lease probes."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class PoolAuditError(RuntimeError):
    pass


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise PoolAuditError(f"json_object_required:{path}")
    return value


def _labels(runner: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for item in runner.get("labels") or []:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str) and name.strip():
            result.append(name.strip())
    return sorted(set(result), key=str.casefold)


PROBE_NAME_PREFIX = "ReqSys DEV runner lease probe"


def audit(policy: dict[str, Any], jobs_payload: dict[str, Any]) -> dict[str, Any]:
    profile_name = policy.get("monitor_profile")
    profiles = policy.get("profiles")
    if not isinstance(profile_name, str) or not isinstance(profiles, dict):
        raise PoolAuditError("monitor_profile_invalid")
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise PoolAuditError("monitor_profile_invalid")
    required = profile.get("runner_labels")
    if not isinstance(required, list) or not required or not all(isinstance(item, str) and item for item in required):
        raise PoolAuditError("profile_runner_labels_invalid")
    minimum = policy.get("minimum_online_runners")
    if not isinstance(minimum, int) or minimum < 2:
        raise PoolAuditError("minimum_online_runners_invalid")
    jobs = jobs_payload.get("jobs")
    if not isinstance(jobs, list):
        raise PoolAuditError("workflow_jobs_invalid")

    required_by_key = {item.casefold(): item for item in required}
    candidates_by_name: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, Any]] = []
    probe_jobs: list[dict[str, Any]] = []

    for raw in jobs:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        if not name.startswith(f"{PROBE_NAME_PREFIX} ("):
            continue
        probe_jobs.append(raw)

    if len(probe_jobs) < minimum:
        findings.append(
            {
                "type": "probe_jobs_missing",
                "observed": len(probe_jobs),
                "required": minimum,
            }
        )

    assigned_probe_jobs = 0
    successful_probe_jobs = 0
    for raw in probe_jobs:
        job_name = str(raw.get("name") or "unknown")
        runner_name = str(raw.get("runner_name") or "").strip()
        labels = _labels(raw)
        label_keys = {item.casefold() for item in labels}
        missing = [label for key, label in required_by_key.items() if key not in label_keys]
        status = str(raw.get("status") or "unknown").casefold()
        conclusion = str(raw.get("conclusion") or "").casefold()
        if runner_name:
            assigned_probe_jobs += 1
        else:
            findings.append({"type": "probe_unassigned", "job": job_name, "status": status})
        if status != "completed":
            findings.append({"type": "probe_incomplete", "job": job_name, "status": status})
        elif conclusion != "success":
            findings.append({"type": "probe_failed", "job": job_name, "conclusion": conclusion or "unknown"})
        runner = {
            "name": runner_name or "unassigned",
            "jobs": [job_name],
            "status": status,
            "conclusion": conclusion or None,
            "labels": labels,
            "missing_labels": missing,
            "eligible": bool(runner_name) and status == "completed" and conclusion == "success" and not missing,
        }
        if missing:
            findings.append(
                {
                    "type": "runner_labels_mismatch",
                    "runner": runner["name"],
                    "job": job_name,
                    "missing_labels": missing,
                }
            )
        if runner["eligible"]:
            successful_probe_jobs += 1
            key = runner_name.casefold()
            existing = candidates_by_name.get(key)
            if existing is None:
                candidates_by_name[key] = runner
            else:
                existing["jobs"].append(job_name)

    candidates = sorted(candidates_by_name.values(), key=lambda item: item["name"].casefold())
    online_eligible = len(candidates)
    if successful_probe_jobs >= minimum and online_eligible < minimum:
        findings.append(
            {
                "type": "probe_runner_reused",
                "successful_probe_jobs": successful_probe_jobs,
                "distinct_runners": online_eligible,
            }
        )
    if online_eligible < minimum:
        findings.append(
            {
                "type": "insufficient_online_runners",
                "observed": online_eligible,
                "required": minimum,
            }
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "pool": policy.get("pool"),
        "environment": "dev",
        "monitored_profile": profile_name,
        "status": "passed" if not findings else "degraded",
        "minimum_online_runners": minimum,
        "online_eligible_runners": online_eligible,
        "probe_jobs_observed": len(probe_jobs),
        "probe_jobs_assigned": assigned_probe_jobs,
        "probe_jobs_successful": successful_probe_jobs,
        "candidate_runners": candidates,
        "findings": findings,
        "mode": "report_only",
        "mutated": False,
        "deploy_performed": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("config/reqsys-dev-runner-pool.json"))
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(load_object(args.policy), load_object(args.jobs))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "online_eligible_runners": result["online_eligible_runners"]}))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed on malformed external inventory.
        print(json.dumps({"status": "blocked", "reason": str(exc)[:500], "production_touched": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
