#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
ENDPOINT = "http://DESKTOP-PDQK954:8787"
TASK_TYPE = "host.rdc.recover.v1"
CONFIRM = "RECOVER-DESKTOP-RDC-VIA-ORCHESTRATOR"
TERMINAL = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}
DEFAULT_TIMEOUT_SECONDS = 90.0


class RecoveryError(RuntimeError):
    pass


Transport = Callable[[str, str, dict[str, Any] | None], tuple[int, dict[str, Any]]]


def request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    if not path.startswith("/") or "://" in path:
        raise RecoveryError("path_not_allowed")
    raw = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT + path,
        data=raw,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ReqSys-Noteri-Desktop-RDC-Recovery/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else {}
            if not isinstance(data, dict):
                raise RecoveryError("response_not_object")
            return int(response.status), data
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}
        return int(exc.code), data if isinstance(data, dict) else {}
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"transport_error:{type(exc).__name__}") from exc


def validate_local_host() -> None:
    if os.name != "nt":
        raise RecoveryError("windows_required")
    if socket.gethostname().casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise RecoveryError("source_host_not_authorized")


def worker_snapshot(transport: Transport) -> dict[str, Any]:
    status, payload = transport("GET", "/v1/workers", None)
    if status != 200:
        raise RecoveryError(f"workers_http_{status}")
    workers = payload.get("workers")
    if not isinstance(workers, list):
        raise RecoveryError("workers_invalid")
    matches = [
        item for item in workers
        if isinstance(item, dict)
        and str(item.get("device_name") or "").casefold() == TARGET_HOST.casefold()
    ]
    if len(matches) != 1:
        raise RecoveryError("desktop_worker_not_unique")
    worker = matches[0]
    capabilities = worker.get("capabilities")
    safe = capabilities.get("safe_task_types") if isinstance(capabilities, dict) else []
    if (
        worker.get("fresh") is not True
        or worker.get("eligible") is not True
        or not isinstance(safe, list)
        or TASK_TYPE not in safe
    ):
        raise RecoveryError("desktop_worker_not_eligible_for_rdc_recovery")
    return {
        "worker_id": str(worker.get("worker_id") or ""),
        "device_name": str(worker.get("device_name") or ""),
        "controller_version": str(worker.get("controller_version") or ""),
        "fresh": True,
        "eligible": True,
        "rdc_capability": True,
    }


def recover(
    correlation_id: str,
    *,
    transport: Transport = request_json,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    correlation = str(correlation_id or "").strip()
    if not 8 <= len(correlation) <= 160:
        raise RecoveryError("correlation_id_invalid")
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise RecoveryError("timeout_invalid")

    ready_status, ready = transport("GET", "/readyz", None)
    if ready_status != 200 or ready.get("ready") is not True:
        raise RecoveryError("orchestrator_not_ready")

    before = worker_snapshot(transport)
    event_id = f"{correlation}-rdc"
    intake = {
        "event_id": event_id,
        "correlation_id": correlation,
        "idempotency_key": f"desktop-rdc-recovery:{correlation}",
        "task_type": TASK_TYPE,
        "payload": {
            "target_host": TARGET_HOST,
            "force_restart": True,
        },
        "risk": 1,
        "max_attempts": 1,
        "lease_seconds": 90,
    }
    status, accepted = transport("POST", "/v1/intake", intake)
    if status not in {200, 201}:
        raise RecoveryError(f"intake_http_{status}")
    item = accepted.get("item")
    if not isinstance(item, dict) or not item.get("id"):
        raise RecoveryError("work_item_missing")
    item_id = str(item["id"])

    deadline = time.monotonic() + timeout_seconds
    observed = item
    while time.monotonic() < deadline:
        state = str(observed.get("status") or "")
        if state in TERMINAL:
            break
        sleep_fn(2.0)
        item_status, snapshot = transport("GET", f"/v1/work-items/{item_id}", None)
        if item_status != 200:
            raise RecoveryError(f"work_item_http_{item_status}")
        loaded = snapshot.get("item")
        if not isinstance(loaded, dict):
            raise RecoveryError("work_item_invalid")
        observed = loaded

    if str(observed.get("status") or "") != "CONCLUÍDO":
        raise RecoveryError(
            "rdc_recovery_not_completed:"
            + str(observed.get("status") or "timeout")
            + ":"
            + str(observed.get("last_error") or "")[:180]
        )
    result = observed.get("result")
    if not isinstance(result, dict):
        raise RecoveryError("result_missing")
    if result.get("handler") != TASK_TYPE:
        raise RecoveryError("handler_mismatch")
    if str(result.get("host") or "").casefold() != TARGET_HOST.casefold():
        raise RecoveryError("result_host_mismatch")
    if str(result.get("device_name") or "").casefold() != TARGET_HOST.casefold():
        raise RecoveryError("executor_host_mismatch")

    return {
        "ok": True,
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "endpoint": ENDPOINT,
        "task_type": TASK_TYPE,
        "correlation_id": correlation,
        "work_item_id": item_id,
        "created": bool(accepted.get("created")),
        "replayed": bool(accepted.get("replayed")),
        "worker_before": before,
        "result": {
            "handler": result.get("handler"),
            "host": result.get("host"),
            "worker_id": result.get("worker_id"),
            "device_name": result.get("device_name"),
            "task": result.get("task"),
            "force_restart": result.get("force_restart"),
            "stopped_for_restart": result.get("stopped_for_restart"),
        },
        "remote_shell_used": False,
        "arbitrary_command_supported": False,
        "production_touched": False,
        "reboot_performed": False,
        "secrets_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    if args.confirm != CONFIRM:
        print(json.dumps({"ok": False, "error": "confirmation_invalid"}, sort_keys=True))
        return 2

    try:
        validate_local_host()
        payload = recover(
            args.correlation_id,
            timeout_seconds=args.timeout_seconds,
        )
        code = 0
    except (RecoveryError, OSError, ValueError) as exc:
        payload = {
            "ok": False,
            "source_host": socket.gethostname(),
            "target_host": TARGET_HOST,
            "endpoint": ENDPOINT,
            "task_type": TASK_TYPE,
            "correlation_id": args.correlation_id,
            "error": str(exc)[:500],
            "remote_shell_used": False,
            "arbitrary_command_supported": False,
            "production_touched": False,
            "reboot_performed": False,
            "secrets_read": False,
        }
        code = 3

    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
