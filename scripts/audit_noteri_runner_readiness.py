#!/usr/bin/env python3
"""Classify a GitHub App authenticated runner inventory without touching any host."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/noteri-runtime"
RUNNER = "Noteri-runtime"
LABELS = frozenset(("self-hosted", "Windows", "X64", "noteri", "reqsys-dev"))
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


class ReadinessError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReadinessError(code)


def classify(inventory: Any, *, source_sha: str, noteri_sha: str,
             run_id: str, run_attempt: str, observed_at: str) -> dict[str, Any]:
    """Check all paginated records. Missing/inconsistent data never means READY."""
    require(bool(SHA40.fullmatch(source_sha)) and bool(SHA40.fullmatch(noteri_sha)),
            "NOTERI_RUNNER_SHA_INVALID")
    require(run_id.isdecimal() and int(run_id) > 0 and
            run_attempt.isdecimal() and int(run_attempt) > 0,
            "NOTERI_RUNNER_RUN_ID_INVALID")
    require(observed_at.endswith("Z"), "NOTERI_RUNNER_TIMESTAMP_INVALID")
    try:
        stamp = dt.datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReadinessError("NOTERI_RUNNER_TIMESTAMP_INVALID") from exc
    require(stamp.tzinfo is not None, "NOTERI_RUNNER_TIMESTAMP_INVALID")
    require(isinstance(inventory, list) and bool(inventory),
            "NOTERI_RUNNER_INVENTORY_PAGES_INVALID")
    all_runners: list[dict[str, Any]] = []
    advertised: int | None = None
    for page in inventory:
        require(isinstance(page, dict) and type(page.get("total_count")) is int
                and page["total_count"] >= 0 and isinstance(page.get("runners"), list),
                "NOTERI_RUNNER_INVENTORY_SCHEMA_INVALID")
        require(advertised is None or advertised == page["total_count"],
                "NOTERI_RUNNER_INVENTORY_COUNT_DRIFT")
        advertised = page["total_count"]
        all_runners.extend(page["runners"])
    require(len(all_runners) == advertised and all(isinstance(r, dict) for r in all_runners),
            "NOTERI_RUNNER_INVENTORY_INCOMPLETE")
    ids = [r.get("id") for r in all_runners]
    require(all(type(i) is int and i > 0 for i in ids) and len(set(ids)) == len(ids),
            "NOTERI_RUNNER_INVENTORY_AMBIGUOUS")
    matches = [r for r in all_runners if r.get("name") == RUNNER]
    require(len(matches) == 1, "NOTERI_RUNNER_NOT_UNIQUE")
    runner = matches[0]
    require(runner.get("os") == "Windows" and
            runner.get("status") in ("online", "offline") and
            type(runner.get("busy")) is bool,
            "NOTERI_RUNNER_STATUS_INVALID")
    raw_labels = runner.get("labels")
    require(isinstance(raw_labels, list) and all(isinstance(x, dict) and
            isinstance(x.get("name"), str) and bool(x["name"]) for x in raw_labels),
            "NOTERI_RUNNER_LABELS_INVALID")
    observed_labels = [x["name"] for x in raw_labels]
    require(len(set(observed_labels)) == len(observed_labels),
            "NOTERI_RUNNER_LABELS_AMBIGUOUS")
    missing = sorted(LABELS - set(observed_labels))
    if missing:
        state = "label_mismatch"
    elif runner["status"] != "online":
        state = "offline"
    elif runner["busy"]:
        state = "busy"
    else:
        state = "available_at_observation"
    return {
        "schema_version": 1,
        "result": "NOTERI_RUNNER_READINESS_OBSERVED",
        "state": state,
        "ready_for_dispatch_precheck": state == "available_at_observation",
        "dispatch_executed": False,
        "authorization_for_host": False,
        "runner_name": RUNNER,
        "runner_id": runner["id"],
        "runner_status": runner["status"],
        "runner_busy": runner["busy"],
        "missing_required_labels": missing,
        "repository": REPO,
        "noteri_sha": noteri_sha,
        "control_plane_sha": source_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "observed_at": observed_at,
        "sample_not_lease": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Noteri runner inventory read-only gate")
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--noteri-sha", required=True)
    parser.add_argument("--control-plane-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--observed-at", required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.inventory.read_text(encoding="utf-8"))
        receipt = classify(data, source_sha=args.control_plane_sha,
                           noteri_sha=args.noteri_sha, run_id=args.run_id,
                           run_attempt=args.run_attempt, observed_at=args.observed_at)
    except (ReadinessError, OSError, UnicodeError, ValueError, TypeError):
        print("NOTERI_RUNNER_READINESS_BLOCKED_INVALID_OR_UNAUTHORIZED_INVENTORY")
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["ready_for_dispatch_precheck"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
