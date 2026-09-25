#!/usr/bin/env python3
"""Recupera o runner GitHub do Desktop exclusivamente via control plane tipado."""

from __future__ import annotations

import argparse
import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
TARGET_WORKER_ID = "desktop-pdqk954"
CONTROL_PLANE = "http://DESKTOP-PDQK954:8787"
EXPECTED_ORCHESTRATOR_SHA = "4dbc927595a40fc2fd6b207c0d53fd6e895049ae"
CONFIRM = "RECOVER-DESKTOP-GITHUB-RUNNER-VIA-CONTROL-PLANE"
REFRESH_TASK = "host.orchestrator.refresh.v1"
BOOTSTRAP_TASK = "host.github_runner.bootstrap.v1"
TERMINAL_STATUSES = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}
RequestFn = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]


class RecoveryError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())[:limit]


def validate_context(
    confirm: str,
    correlation_id: str,
    *,
    host: str | None = None,
    platform: str | None = None,
) -> str:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise RecoveryError(f"source_host_not_allowed:{actual_host}")
    if actual_platform != "nt":
        raise RecoveryError("windows_required")
    correlation = correlation_id.strip()
    if not 8 <= len(correlation) <= 160:
        raise RecoveryError("correlation_id_invalid")
    return correlation


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.startswith("/"):
        raise RecoveryError("relative_control_plane_path_required")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        CONTROL_PLANE + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RecoveryError(f"control_plane_http_{exc.code}") from exc
    except (URLError, OSError, TimeoutError) as exc:
        raise RecoveryError("control_plane_unreachable") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RecoveryError("control_plane_invalid_json") from exc
    if not isinstance(data, dict):
        raise RecoveryError("control_plane_response_not_object")
    return data


def worker_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    workers = snapshot.get("workers")
    if not isinstance(workers, list):
        raise RecoveryError("workers_snapshot_invalid")
    matches = [
        item
        for item in workers
        if isinstance(item, dict) and item.get("worker_id") == TARGET_WORKER_ID
    ]
    if len(matches) != 1:
        raise RecoveryError("desktop_worker_not_unique")
    worker = matches[0]
    if str(worker.get("device_name") or "").casefold() != TARGET_HOST.casefold():
        raise RecoveryError("desktop_worker_host_mismatch")
    if worker.get("fresh") is not True or worker.get("eligible") is not True:
        raise RecoveryError("desktop_worker_not_eligible")
    capabilities = worker.get("capabilities")
    if not isinstance(capabilities, dict):
        raise RecoveryError("desktop_worker_capabilities_invalid")
    return worker


def safe_task_types(worker: dict[str, Any]) -> set[str]:
    raw = (worker.get("capabilities") or {}).get("safe_task_types")
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise RecoveryError("desktop_worker_safe_task_types_invalid")
    return set(raw)


def submit(
    request: RequestFn,
    *,
    task_type: str,
    correlation_id: str,
    idempotency_suffix: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = request(
        "POST",
        "/v1/work-items",
        {
            "event_id": f"{correlation_id}:{idempotency_suffix}",
            "correlation_id": correlation_id,
            "idempotency_key": f"desktop-runner-recovery:{correlation_id}:{idempotency_suffix}",
            "task_type": task_type,
            "payload": payload,
            "risk": 2,
            "max_attempts": 1,
        },
    )
    item = response.get("item")
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        raise RecoveryError("work_item_submission_invalid")
    return item


def wait_item(
    request: RequestFn,
    item_id: str,
    *,
    timeout_seconds: float = 90.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        item = request("GET", f"/v1/work-items/{item_id}", None).get("item")
        if not isinstance(item, dict):
            raise RecoveryError("work_item_readback_invalid")
        status = item.get("status")
        if status in TERMINAL_STATUSES:
            return item
        sleep_fn(1.0)
    raise RecoveryError(f"work_item_timeout:{item_id}")


def wait_for_bootstrap_capability(
    request: RequestFn,
    *,
    timeout_seconds: float = 150.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not_observed"
    while time.monotonic() < deadline:
        try:
            worker = worker_from_snapshot(request("GET", "/v1/workers", None))
            if BOOTSTRAP_TASK in safe_task_types(worker):
                return worker
            last_error = "bootstrap_capability_absent"
        except RecoveryError as exc:
            last_error = sanitize(exc)
        sleep_fn(2.0)
    raise RecoveryError(f"runtime_refresh_readback_timeout:{last_error}")


def recover(
    *,
    confirm: str,
    correlation_id: str,
    evidence_file: Path,
    request: RequestFn = request_json,
    sleep_fn: Callable[[float], None] = time.sleep,
    source_host: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    correlation = validate_context(
        confirm,
        correlation_id,
        host=source_host,
        platform=platform,
    )
    before = worker_from_snapshot(request("GET", "/v1/workers", None))
    before_tasks = safe_task_types(before)
    capabilities = before.get("capabilities") or {}
    if REFRESH_TASK not in before_tasks:
        raise RecoveryError("runtime_refresh_capability_missing")
    if capabilities.get("recovery_contract_version") != 1:
        raise RecoveryError("recovery_contract_v1_required")

    refresh = submit(
        request,
        task_type=REFRESH_TASK,
        correlation_id=correlation,
        idempotency_suffix="refresh",
        payload={
            "target_host": TARGET_HOST,
            "expected_sha": EXPECTED_ORCHESTRATOR_SHA,
        },
    )
    refresh_terminal = wait_item(
        request,
        refresh["id"],
        timeout_seconds=90.0,
        sleep_fn=sleep_fn,
    )
    if refresh_terminal.get("status") != "CONCLUÍDO":
        raise RecoveryError(
            f"runtime_refresh_not_completed:{refresh_terminal.get('status')}"
        )
    refresh_result = refresh_terminal.get("result") or {}
    if refresh_result.get("expected_sha") != EXPECTED_ORCHESTRATOR_SHA:
        raise RecoveryError("runtime_refresh_sha_not_acknowledged")

    after = wait_for_bootstrap_capability(
        request,
        timeout_seconds=150.0,
        sleep_fn=sleep_fn,
    )
    after_tasks = safe_task_types(after)
    if BOOTSTRAP_TASK not in after_tasks:
        raise RecoveryError("runner_bootstrap_capability_missing_after_refresh")

    bootstrap = submit(
        request,
        task_type=BOOTSTRAP_TASK,
        correlation_id=correlation,
        idempotency_suffix="bootstrap",
        payload={
            "target_host": TARGET_HOST,
            # Deliberately untrusted extra input: the worker contract must ignore it.
            "runner_home": "C:/untrusted-must-be-ignored",
        },
    )
    bootstrap_terminal = wait_item(
        request,
        bootstrap["id"],
        timeout_seconds=90.0,
        sleep_fn=sleep_fn,
    )
    if bootstrap_terminal.get("status") != "CONCLUÍDO":
        raise RecoveryError(
            f"runner_bootstrap_not_completed:{bootstrap_terminal.get('status')}"
        )
    result = bootstrap_terminal.get("result")
    if not isinstance(result, dict):
        raise RecoveryError("runner_bootstrap_result_invalid")
    if result.get("local_listener_verified") is not True:
        raise RecoveryError("runner_listener_not_verified")
    if result.get("pickup_required") is not True:
        raise RecoveryError("independent_pickup_contract_missing")
    if result.get("secrets_read") is not False or result.get("production_touched") is not False:
        raise RecoveryError("runner_bootstrap_safety_contract_failed")
    if str(result.get("runner_home") or "").replace("\\", "/").casefold() == "c:/untrusted-must-be-ignored".casefold():
        raise RecoveryError("untrusted_runner_home_was_accepted")

    evidence = {
        "schema_version": "1",
        "ok": True,
        "result": "DESKTOP_GITHUB_RUNNER_BOOTSTRAP_LOCAL_OK",
        "generated_at_utc": now_iso(),
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "target_worker_id": TARGET_WORKER_ID,
        "control_plane": CONTROL_PLANE,
        "expected_orchestrator_sha": EXPECTED_ORCHESTRATOR_SHA,
        "recovery_contract_version": 1,
        "refresh_work_item_id": refresh["id"],
        "refresh_terminal_status": refresh_terminal.get("status"),
        "bootstrap_work_item_id": bootstrap["id"],
        "bootstrap_terminal_status": bootstrap_terminal.get("status"),
        "bootstrap_capability_readback": BOOTSTRAP_TASK in after_tasks,
        "local_listener_verified": True,
        "github_pickup_required": True,
        "untrusted_runner_home_ignored": True,
        "correlation_id": correlation,
        "remote_shell_used": False,
        "rdc_used": False,
        "wmi_used": False,
        "secrets_read": False,
        "production_touched": False,
        "reboot_performed": False,
    }
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = recover(
            confirm=args.confirm,
            correlation_id=args.correlation_id,
            evidence_file=args.evidence_file.resolve(),
        )
    except (RecoveryError, OSError) as exc:
        result = {
            "schema_version": "1",
            "ok": False,
            "result": "DESKTOP_GITHUB_RUNNER_BOOTSTRAP_BLOCKED",
            "error_type": type(exc).__name__,
            "error": sanitize(exc),
            "correlation_id": args.correlation_id,
            "remote_shell_used": False,
            "rdc_used": False,
            "wmi_used": False,
            "secrets_read": False,
            "production_touched": False,
            "reboot_performed": False,
            "generated_at_utc": now_iso(),
        }
        args.evidence_file.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.resolve().write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
