#!/usr/bin/env python3
"""Smoke DEV fail-closed do Codex Worker Pool em lane sintética desabilitada."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pending_development_worker_pool_bridge import (  # noqa: E402
    BridgeError,
    direct_report,
    enqueue_local_work,
    http_request,
    read_token,
    resolve_token_file,
    validate_pool_url,
    write_evidence,
)

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SMOKE_REPOSITORY = "ericson-j-santos/codex-worker-pool-smoke"
SMOKE_ISSUE = 1914


def current_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip().lower()


def run_smoke(
    *,
    expected_sha: str,
    correlation_id: str,
    pool_url: str,
    token_file: Path | None,
) -> dict[str, Any]:
    expected_sha = expected_sha.strip().lower()
    if not SHA40.fullmatch(expected_sha):
        raise BridgeError("expected_sha_invalid")
    if current_sha() != expected_sha:
        raise BridgeError("checkout_sha_mismatch")
    if not correlation_id.strip():
        raise BridgeError("correlation_id_invalid")

    pool_url = validate_pool_url(pool_url)
    token = read_token(token_file)

    lane_payload = {
        "repository": SMOKE_REPOSITORY,
        "enabled": False,
        "max_in_flight": 1,
        "correlation_id": f"{correlation_id}-lane"[:128],
    }
    code, configured = http_request(
        "POST", f"{pool_url}/v1/repositories", token, lane_payload
    )
    if code != 200:
        raise BridgeError("worker_pool_smoke_lane_config_failed")
    if configured.get("repository") != SMOKE_REPOSITORY:
        raise BridgeError("worker_pool_smoke_lane_repository_mismatch")
    if configured.get("enabled") is not False:
        raise BridgeError("worker_pool_smoke_lane_not_disabled")

    report = direct_report(
        SMOKE_REPOSITORY,
        SMOKE_ISSUE,
        f"smoke-{expected_sha[:12]}",
        correlation_id,
    )
    handoff = enqueue_local_work(
        report,
        base_sha=expected_sha,
        pool_url=pool_url,
        token=token,
    )
    if handoff.get("result") != "WORKER_POOL_ENQUEUED":
        raise BridgeError("worker_pool_smoke_enqueue_failed")
    items = handoff.get("items") or []
    if len(items) != 1:
        raise BridgeError("worker_pool_smoke_item_count")
    item = items[0]
    if item.get("replay_created") is not False or item.get("independent_readback") is not True:
        raise BridgeError("worker_pool_smoke_idempotency_not_proven")

    code, snapshot = http_request("GET", f"{pool_url}/v1/snapshot", token, None)
    if code != 200:
        raise BridgeError("worker_pool_smoke_snapshot_failed")
    lane = next(
        (
            row
            for row in snapshot.get("repositories") or []
            if row.get("repository") == SMOKE_REPOSITORY
        ),
        None,
    )
    if not isinstance(lane, dict) or lane.get("enabled") is not False:
        raise BridgeError("worker_pool_smoke_lane_readback_failed")

    task_id = str(item.get("task_id") or "")
    task = next(
        (
            row
            for row in snapshot.get("tasks") or []
            if row.get("task_id") == task_id
        ),
        None,
    )
    if not isinstance(task, dict):
        raise BridgeError("worker_pool_smoke_task_missing_from_snapshot")
    if task.get("state") != "queued" or task.get("leased_by") is not None:
        raise BridgeError("worker_pool_smoke_task_became_executable")

    return {
        "schema_version": "1.0.0",
        "result": "WORKER_POOL_SMOKE_PASSED",
        "correlation_id": correlation_id,
        "expected_sha": expected_sha,
        "repository": SMOKE_REPOSITORY,
        "lane_enabled": False,
        "task_id": task_id,
        "task_state": task.get("state"),
        "leased_by": None,
        "replay_created": False,
        "independent_readback": True,
        "secrets_exposed": False,
        "production_touched": False,
        "deploy_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke DEV do Codex Worker Pool")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument(
        "--pool-url",
        default=os.getenv("CODEX_WORKER_POOL_URL", "http://127.0.0.1:8097"),
    )
    parser.add_argument("--token-file", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/codex-worker-pool-smoke-dev/evidence.json"),
    )
    args = parser.parse_args()

    try:
        token_file = resolve_token_file(args.token_file)
        result = run_smoke(
            expected_sha=args.expected_sha,
            correlation_id=args.correlation_id,
            pool_url=args.pool_url,
            token_file=token_file,
        )
        write_evidence(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (BridgeError, OSError, subprocess.CalledProcessError) as exc:
        blocked = {
            "schema_version": "1.0.0",
            "result": "WORKER_POOL_SMOKE_BLOCKED",
            "reason": str(exc)[:240],
            "production_touched": False,
            "deploy_executed": False,
        }
        write_evidence(args.output, blocked)
        print(json.dumps(blocked, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
