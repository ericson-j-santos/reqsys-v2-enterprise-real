#!/usr/bin/env python3
"""Build sanitized, report-only evidence for the ReqSys DEV runner pool."""

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


def audit(policy: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    required = policy.get("runner_labels")
    if not isinstance(required, list) or not required or not all(isinstance(item, str) and item for item in required):
        raise PoolAuditError("runner_labels_invalid")
    minimum = policy.get("minimum_online_runners")
    if not isinstance(minimum, int) or minimum < 2:
        raise PoolAuditError("minimum_online_runners_invalid")
    runners = inventory.get("runners")
    if not isinstance(runners, list):
        raise PoolAuditError("runner_inventory_invalid")

    required_by_key = {item.casefold(): item for item in required}
    candidates: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for raw in runners:
        if not isinstance(raw, dict):
            continue
        labels = _labels(raw)
        label_keys = {item.casefold() for item in labels}
        if "reqsys-dev" not in label_keys and policy["pool"].casefold() not in label_keys:
            continue
        missing = [label for key, label in required_by_key.items() if key not in label_keys]
        status = str(raw.get("status") or "unknown").casefold()
        runner = {
            "id": raw.get("id"),
            "name": str(raw.get("name") or "unknown"),
            "status": status,
            "busy": raw.get("busy") is True,
            "labels": labels,
            "missing_labels": missing,
            "eligible": status == "online" and not missing,
        }
        candidates.append(runner)
        if status != "online":
            findings.append({"type": "runner_offline", "runner": runner["name"], "status": status})
        if missing:
            findings.append({"type": "runner_labels_mismatch", "runner": runner["name"], "missing_labels": missing})

    online_eligible = sum(1 for runner in candidates if runner["eligible"])
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
        "status": "passed" if not findings else "degraded",
        "minimum_online_runners": minimum,
        "online_eligible_runners": online_eligible,
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
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(load_object(args.policy), load_object(args.inventory))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "online_eligible_runners": result["online_eligible_runners"]}))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)[:500], "production_touched": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
