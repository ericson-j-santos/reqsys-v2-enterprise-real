#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = "http://DESKTOP-PDQK954:8787"
WORKER_ID = "desktop-pdqk954"
TASK_TYPE = "host.github_runner.recover.v1"
TARGET_HOST = "DESKTOP-PDQK954"
CONFIRM = "RECOVER-DESKTOP-RUNNER-VIA-ORCHESTRATOR"
TERMINAL = {"completed", "failed", "blocked", "quarantined", "cancelled"}


class RecoveryError(RuntimeError):
    pass


def _request(method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 5.0) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return int(response.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RecoveryError(f"http_{exc.code}:{raw[:200]}") from exc
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"transport_error:{type(exc).__name__}") from exc


def _workers() -> list[dict[str, Any]]:
    status, payload = _request("GET", "/v1/workers")
    if status != 200:
        raise RecoveryError(f"workers_http_{status}")
    workers = payload.get("workers")
    if not isinstance(workers, list):
        raise RecoveryError("workers_payload_invalid")
    return [item for item in workers if isinstance(item, dict)]


def _desktop_worker() -> dict[str, Any]:
    matches = [
        item for item in _workers()
        if str(item.get("worker_id") or "").casefold() == WORKER_ID
    ]
    if len(matches) != 1:
        raise RecoveryError(f"desktop_worker_match_count_{len(matches)}")
    return matches[0]


def _safe_task_types(worker: dict[str, Any]) -> list[str]:
    capabilities = worker.get("capabilities")
    if not isinstance(capabilities, dict):
        return []
    values = capabilities.get("safe_task_types")
    return [str(x) for x in values] if isinstance(values, list) else []


def recover(correlation_id: str, timeout_seconds: int) -> dict[str, Any]:
    worker_before = _desktop_worker()
    safe_types = _safe_task_types(worker_before)
    if TASK_TYPE not in safe_types:
        raise RecoveryError("desktop_worker_capability_missing:host.github_runner.recover.v1")

    event_id = f"{correlation_id}:event"
    idempotency_key = f"{correlation_id}:runner-recovery"
    payload = {
        "event_id": event_id,
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "task_type": TASK_TYPE,
        "payload": {"target_host": TARGET_HOST},
        "risk": 1,
        "max_attempts": 1,
        "lease_seconds": 60,
    }
    status, created = _request("POST", "/v1/intake", payload)
    if status not in {200, 201}:
        raise RecoveryError(f"intake_http_{status}")

    item = created.get("item") if isinstance(created, dict) else None
    if not isinstance(item, dict) or not item.get("id"):
        raise RecoveryError("work_item_missing")
    item_id = str(item["id"])
    dispatch = created.get("dispatch")
    if not isinstance(dispatch, dict):
        raise RecoveryError("work_item_not_dispatched")
    worker = dispatch.get("worker")
    if not isinstance(worker, dict) or str(worker.get("worker_id") or "").casefold() != WORKER_ID:
        raise RecoveryError("dispatch_worker_mismatch")

    deadline = time.monotonic() + timeout_seconds
    observed = item
    while time.monotonic() < deadline:
        _, current = _request("GET", f"/v1/work-items/{item_id}")
        candidate = current.get("item") if isinstance(current, dict) else None
        if isinstance(candidate, dict):
            observed = candidate
            state = str(candidate.get("state") or "").casefold()
            if state in TERMINAL:
                break
        time.sleep(2)

    state = str(observed.get("state") or "").casefold()
    if state != "completed":
        raise RecoveryError(f"runner_recovery_not_completed:{state or 'unknown'}")

    result = observed.get("result")
    if not isinstance(result, dict):
        raise RecoveryError("runner_recovery_result_missing")
    if str(result.get("handler") or "") != TASK_TYPE:
        raise RecoveryError("runner_recovery_handler_mismatch")

    worker_after = _desktop_worker()
    return {
        "ok": True,
        "environment": "dev",
        "target_host": TARGET_HOST,
        "transport": "noteri_to_desktop_orchestrator_8787",
        "task_type": TASK_TYPE,
        "correlation_id": correlation_id,
        "event_id": event_id,
        "idempotency_key": idempotency_key,
        "work_item_id": item_id,
        "final_state": state,
        "result": result,
        "worker_before": {
            "fresh": worker_before.get("fresh") is True,
            "controller_online": worker_before.get("controller_online") is True,
            "auth_valid": worker_before.get("auth_valid") is True,
            "safe_task_types": safe_types,
        },
        "worker_after": {
            "fresh": worker_after.get("fresh") is True,
            "controller_online": worker_after.get("controller_online") is True,
            "auth_valid": worker_after.get("auth_valid") is True,
            "safe_task_types": _safe_task_types(worker_after),
        },
        "remote_shell_used": False,
        "production_touched": False,
        "reboot_performed": False,
        "secrets_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args()
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)

    if args.confirm != CONFIRM:
        payload = {"ok": False, "error": "confirmation_invalid", "production_touched": False}
        args.evidence_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, sort_keys=True))
        return 2

    try:
        payload = recover(args.correlation_id.strip(), max(10, min(args.timeout_seconds, 120)))
        code = 0
    except RecoveryError as exc:
        payload = {
            "ok": False,
            "environment": "dev",
            "target_host": TARGET_HOST,
            "transport": "noteri_to_desktop_orchestrator_8787",
            "task_type": TASK_TYPE,
            "correlation_id": args.correlation_id.strip(),
            "error": str(exc),
            "remote_shell_used": False,
            "production_touched": False,
            "reboot_performed": False,
            "secrets_read": False,
        }
        code = 3

    args.evidence_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
