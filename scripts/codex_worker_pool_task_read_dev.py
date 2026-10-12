#!/usr/bin/env python3
"""Read exactly the previously enqueued ReqSys DEV task; no claim or requeue."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOST = "DESKTOP-PDQK954"
TASK_ID = "cwp-cdb85c31e3cc4e972f3094ab"
REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
ISSUE_NUMBER = 2546
REQUEST_ID = "4f6f18810783cdc6872f04f1"
BASE_SHA = "14232beac63c8d202f90bed1cf23df8680a54b2e"
POOL_URL = "http://127.0.0.1:8097"
EVIDENCE = ROOT / "artifacts" / "codex-worker-pool-task-read-dev" / "evidence.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
STATES = {"queued", "leased", "running", "validating", "blocked", "completed", "failed"}
HTTP = Callable[[str, str, str, dict[str, Any] | None], tuple[int, dict[str, Any]]]


class TaskReadError(RuntimeError):
    """Codes only: never include server response or raw exception text."""


def current_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip().lower()


def safe_worker_hash(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", value):
        raise TaskReadError("worker_identity_invalid")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def validated_task(task: Any, *, expected_sha: str) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise TaskReadError("task_payload_invalid")
    identity = {
        "task_id": TASK_ID,
        "repository": REPOSITORY,
        "issue_number": ISSUE_NUMBER,
        "request_id": REQUEST_ID,
        "base_sha": BASE_SHA,
    }
    if any(task.get(field) != value for field, value in identity.items()):
        raise TaskReadError("task_identity_mismatch")
    state = task.get("state")
    if state not in STATES:
        raise TaskReadError("task_state_invalid")
    attempts, max_attempts = task.get("attempt_count"), task.get("max_attempts")
    if (
        type(attempts) is not int
        or type(max_attempts) is not int
        or not (0 <= attempts <= max_attempts <= 20)
    ):
        raise TaskReadError("task_attempts_invalid")
    produced = task.get("produced_sha")
    if produced is not None and (not isinstance(produced, str) or not SHA40.fullmatch(produced)):
        raise TaskReadError("produced_sha_invalid")
    leased = safe_worker_hash(task.get("leased_by"))
    if state == "queued" and leased is not None:
        raise TaskReadError("queued_task_has_lease")
    blocked_reason = task.get("blocked_reason")
    reason_code = None
    if blocked_reason is not None:
        if isinstance(blocked_reason, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,79}", blocked_reason):
            reason_code = blocked_reason
        else:
            reason_code = "redacted"
    return {
        "schema_version": "1.0.0",
        "result": "WORKER_POOL_TASK_READ_OK",
        "environment": "dev",
        "host": HOST,
        "source_sha": expected_sha,
        "task_id": TASK_ID,
        "repository": REPOSITORY,
        "issue_number": ISSUE_NUMBER,
        "request_id": REQUEST_ID,
        "base_sha": BASE_SHA,
        "state": state,
        "attempt_count": attempts,
        "max_attempts": max_attempts,
        "leased": leased is not None,
        "leased_by_sha256_prefix": leased,
        "builder_worker_sha256_prefix": safe_worker_hash(task.get("builder_worker_id")),
        "validator_worker_sha256_prefix": safe_worker_hash(task.get("validator_worker_id")),
        "produced_sha": produced,
        "blocked_reason_code": reason_code,
        "last_material_progress_recorded": bool(task.get("last_material_progress_at")),
        "worker_eligibility_checked": False,
        "why_idle_checked": False,
        "snapshot_called": False,
        "api_methods": ["GET /v1/tasks/{fixed_task_id}"],
        "secrets_exposed": False,
        "production_touched": False,
        "runtime_mutated": False,
        "deploy_executed": False,
    }


def probe_task(
    *,
    expected_sha: str,
    token: str,
    host: str,
    observed_sha: str,
    request_fn: HTTP,
) -> dict[str, Any]:
    if not SHA40.fullmatch(expected_sha):
        raise TaskReadError("expected_sha_invalid")
    if observed_sha != expected_sha:
        raise TaskReadError("checkout_sha_mismatch")
    if host.upper() != HOST:
        raise TaskReadError("host_identity_refused")
    if not isinstance(token, str) or not token:
        raise TaskReadError("token_unavailable")
    status, task = request_fn("GET", f"{POOL_URL}/v1/tasks/{TASK_ID}", token, None)
    if status != 200:
        raise TaskReadError("task_http_not_ok")
    return validated_task(task, expected_sha=expected_sha)


def write_evidence(evidence: dict[str, Any]) -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fixed ReqSys DEV Worker Pool task read")
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        # Validate host and source BEFORE opening the protected token file.
        if socket.gethostname().upper() != HOST:
            raise TaskReadError("host_identity_refused")
        if not SHA40.fullmatch(args.expected_sha) or current_sha() != args.expected_sha:
            raise TaskReadError("checkout_sha_mismatch")
        from scripts.pending_development_worker_pool_bridge import (  # noqa: PLC0415
            http_request,
            read_token,
            resolve_token_file,
        )
        token = read_token(resolve_token_file(None))
        data = probe_task(
            expected_sha=args.expected_sha,
            token=token,
            host=socket.gethostname(),
            observed_sha=args.expected_sha,
            request_fn=http_request,
        )
    except Exception as exc:  # noqa: BLE001 - sanitized error category only
        reason = str(exc) if isinstance(exc, TaskReadError) else "worker_pool_task_read_unavailable"
        write_evidence({
            "schema_version": "1.0.0",
            "result": "WORKER_POOL_TASK_READ_BLOCKED",
            "reason": reason,
            "task_id": TASK_ID,
            "snapshot_called": False,
            "production_touched": False,
            "runtime_mutated": False,
            "secrets_exposed": False,
        })
        print(json.dumps({"result": "WORKER_POOL_TASK_READ_BLOCKED", "reason": reason}))
        return 2
    write_evidence(data)
    print(json.dumps(data, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
