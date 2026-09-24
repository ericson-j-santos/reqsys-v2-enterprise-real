#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTROL_PLANE = "http://DESKTOP-PDQK954:8787"
TARGET_HOST = "DESKTOP-PDQK954"
TASK_TYPE = "host.github_runner.recover.v1"
CONFIRM = "RECOVER-DESKTOP-GITHUB-RUNNER-VIA-ORCHESTRATOR"
TERMINAL = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}


class RecoveryError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    if method not in {"GET", "POST"}:
        raise RecoveryError("method_not_allowlisted")
    if path not in {"/v1/workers", "/v1/intake"} and not path.startswith("/v1/work-items/"):
        raise RecoveryError("path_not_allowlisted")
    data = None
    headers = {"Accept": "application/json", "Cache-Control": "no-store"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(CONTROL_PLANE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RecoveryError(f"control_plane_http_{int(exc.code)}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RecoveryError("control_plane_unreachable") from exc
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RecoveryError("control_plane_invalid_json") from exc
    if not isinstance(decoded, dict):
        raise RecoveryError("control_plane_invalid_payload")
    return status, decoded


def desktop_worker() -> dict[str, Any]:
    _, payload = request_json("GET", "/v1/workers")
    workers = payload.get("workers")
    if not isinstance(workers, list):
        raise RecoveryError("worker_registry_invalid")
    matches = [
        item for item in workers
        if isinstance(item, dict)
        and str(item.get("device_name") or "").casefold() == TARGET_HOST.casefold()
    ]
    if len(matches) != 1:
        raise RecoveryError("desktop_worker_not_unique")
    worker = matches[0]
    caps = worker.get("capabilities")
    if not isinstance(caps, dict):
        raise RecoveryError("desktop_capabilities_invalid")
    safe = caps.get("safe_task_types")
    if not isinstance(safe, list) or TASK_TYPE not in safe:
        raise RecoveryError("desktop_runner_recovery_capability_missing")
    roles = worker.get("roles")
    if not isinstance(roles, list) or "builder" not in roles:
        raise RecoveryError("desktop_builder_role_missing")
    if worker.get("fresh") is not True:
        raise RecoveryError("desktop_worker_stale")
    if worker.get("controller_online") is not True:
        raise RecoveryError("desktop_controller_offline")
    if worker.get("auth_valid") is not True:
        raise RecoveryError("desktop_worker_auth_invalid")
    if str(worker.get("profile") or "").upper() != "NORMAL":
        raise RecoveryError("desktop_profile_not_normal")
    if "eligible" in worker and worker.get("eligible") is not True:
        raise RecoveryError("desktop_worker_not_eligible")
    return {
        "worker_id": str(worker.get("worker_id") or ""),
        "fresh": True,
        "controller_online": True,
        "auth_valid": True,
        "profile": "NORMAL",
        "capability_present": True,
    }


def recover(correlation_id: str) -> dict[str, Any]:
    before = desktop_worker()
    digest = hashlib.sha256(f"desktop-runner-recovery|{correlation_id}".encode("utf-8")).hexdigest()
    _, intake = request_json(
        "POST",
        "/v1/intake",
        {
            "event_id": f"desktop-runner-recovery-{digest[:32]}",
            "correlation_id": correlation_id,
            "idempotency_key": f"desktop-runner-recovery:{digest}",
            "task_type": TASK_TYPE,
            "payload": {"target_host": TARGET_HOST, "worker_hint": "builder"},
            "risk": 2,
            "max_attempts": 1,
            "lease_seconds": 60,
        },
    )
    item = intake.get("item")
    dispatch = intake.get("dispatch")
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        raise RecoveryError("intake_item_invalid")
    if not isinstance(dispatch, dict):
        raise RecoveryError("desktop_recovery_not_dispatched")
    worker = dispatch.get("worker")
    if not isinstance(worker, dict) or str(worker.get("device_name") or "").casefold() != TARGET_HOST.casefold():
        raise RecoveryError("dispatch_target_mismatch")

    item_id = item["id"]
    deadline = time.monotonic() + 35.0
    terminal = None
    while time.monotonic() < deadline:
        _, snapshot = request_json("GET", f"/v1/work-items/{item_id}")
        observed = snapshot.get("item")
        if not isinstance(observed, dict):
            raise RecoveryError("work_item_snapshot_invalid")
        status = str(observed.get("status") or "")
        if status == "CONCLUÍDO":
            terminal = observed
            break
        if status in TERMINAL:
            raise RecoveryError(f"work_item_terminal_{status.lower()}")
        time.sleep(0.5)
    if terminal is None:
        raise RecoveryError("desktop_recovery_timeout")

    result = terminal.get("result")
    if not isinstance(result, dict):
        raise RecoveryError("desktop_recovery_result_invalid")
    if result.get("handler") != TASK_TYPE:
        raise RecoveryError("desktop_recovery_handler_mismatch")
    if str(result.get("host") or "").casefold() != TARGET_HOST.casefold():
        raise RecoveryError("desktop_recovery_host_mismatch")
    if str(result.get("worker_id") or "") != before["worker_id"]:
        raise RecoveryError("desktop_recovery_worker_mismatch")
    if result.get("result") not in {"recovered", "already_running"}:
        raise RecoveryError("desktop_recovery_unexpected_result")
    if result.get("mode") not in {"service", "scheduled_task"}:
        raise RecoveryError("desktop_recovery_mode_invalid")

    after = desktop_worker()
    return {
        "ok": True,
        "task_type": TASK_TYPE,
        "target_host": TARGET_HOST,
        "work_item_id": item_id,
        "created": intake.get("created") is True,
        "replayed": intake.get("replayed") is True,
        "dispatch_worker_id": before["worker_id"],
        "worker_before": before,
        "worker_after": after,
        "handler_result": {
            "mode": result.get("mode"),
            "result": result.get("result"),
            "started": result.get("started") is True,
            "before_state": result.get("before_state"),
            "after_state": result.get("after_state"),
        },
        "correlation_id": correlation_id,
        "production_touched": False,
        "secrets_read": False,
        "observed_at": now_iso(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.confirm != CONFIRM:
            raise RecoveryError("confirmation_invalid")
        if socket.gethostname().casefold() != "noteri":
            raise RecoveryError("source_host_not_noteri")
        correlation_id = args.correlation_id.strip()
        if not 8 <= len(correlation_id) <= 160:
            raise RecoveryError("correlation_id_invalid")
        payload = recover(correlation_id)
        code = 0
    except (RecoveryError, OSError) as exc:
        payload = {
            "ok": False,
            "task_type": TASK_TYPE,
            "target_host": TARGET_HOST,
            "error_code": str(exc),
            "correlation_id": args.correlation_id,
            "production_touched": False,
            "secrets_read": False,
            "observed_at": now_iso(),
        }
        code = 2
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
