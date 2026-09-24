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
REFRESH_TASK_TYPE = "host.orchestrator.refresh.v1"
EXPECTED_RUNTIME_SHA = "63d26ff024e9f782bdddb7e954a6e247c8ef13b7"
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


def desktop_worker(*, require_runner_capability: bool = False) -> dict[str, Any]:
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
    if not isinstance(safe, list):
        raise RecoveryError("desktop_safe_task_types_invalid")
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
    safe_set = {str(value) for value in safe}
    if require_runner_capability and TASK_TYPE not in safe_set:
        raise RecoveryError("desktop_runner_recovery_capability_missing")
    return {
        "worker_id": str(worker.get("worker_id") or ""),
        "fresh": True,
        "controller_online": True,
        "auth_valid": True,
        "profile": "NORMAL",
        "runner_recovery_capability": TASK_TYPE in safe_set,
        "runtime_refresh_capability": REFRESH_TASK_TYPE in safe_set,
    }


def enqueue_and_wait(
    task_type: str,
    *,
    payload: dict[str, Any],
    correlation_id: str,
    timeout_seconds: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    digest = hashlib.sha256(
        f"{task_type}|{correlation_id}".encode("utf-8")
    ).hexdigest()
    _, intake = request_json(
        "POST",
        "/v1/intake",
        {
            "event_id": f"desktop-maintenance-{digest[:32]}",
            "correlation_id": correlation_id,
            "idempotency_key": f"desktop-maintenance:{digest}",
            "task_type": task_type,
            "payload": payload,
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
        raise RecoveryError(f"{task_type}:not_dispatched")
    worker = dispatch.get("worker")
    if (
        not isinstance(worker, dict)
        or str(worker.get("device_name") or "").casefold() != TARGET_HOST.casefold()
    ):
        raise RecoveryError(f"{task_type}:dispatch_target_mismatch")

    item_id = item["id"]
    deadline = time.monotonic() + timeout_seconds
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
            error = str(observed.get("error") or "")[:160]
            raise RecoveryError(f"{task_type}:terminal_{status.lower()}:{error}")
        time.sleep(0.5)
    if terminal is None:
        raise RecoveryError(f"{task_type}:timeout")
    result = terminal.get("result")
    if not isinstance(result, dict):
        raise RecoveryError(f"{task_type}:result_invalid")
    return intake, result


def wait_for_refreshed_worker(timeout_seconds: float = 50.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not_observed"
    while time.monotonic() < deadline:
        try:
            worker = desktop_worker()
            if worker["runner_recovery_capability"]:
                return worker
            last_error = "runner_capability_not_yet_present"
        except RecoveryError as exc:
            last_error = str(exc)
        time.sleep(1.0)
    raise RecoveryError(f"runtime_refresh_readback_timeout:{last_error}")



def recover_via_remote_scm() -> dict[str, Any]:
    if socket.gethostname().casefold() != "noteri":
        raise RecoveryError("remote_scm_source_not_noteri")
    try:
        import win32service
    except ImportError as exc:
        raise RecoveryError("remote_scm_pywin32_unavailable") from exc

    scm_handle = None
    service_handle = None
    try:
        access = (
            win32service.SC_MANAGER_CONNECT
            | win32service.SC_MANAGER_ENUMERATE_SERVICE
        )
        scm_handle = win32service.OpenSCManager(TARGET_HOST, None, access)
        entries = win32service.EnumServicesStatus(
            scm_handle,
            win32service.SERVICE_WIN32,
            win32service.SERVICE_STATE_ALL,
        )
        candidates: list[tuple[str, str, int]] = []
        for service_name, display_name, status in entries:
            haystack = f"{service_name} {display_name}".casefold()
            if "actions.runner" not in haystack and "github actions runner" not in haystack:
                continue
            current_state = int(status[1])
            candidates.append((str(service_name), str(display_name), current_state))

        if len(candidates) == 0:
            raise RecoveryError("remote_scm_github_runner_service_not_found")
        if len(candidates) > 1:
            raise RecoveryError("remote_scm_multiple_github_runner_services")

        service_name, _display_name, before_state = candidates[0]
        service_handle = win32service.OpenService(
            scm_handle,
            service_name,
            win32service.SERVICE_QUERY_STATUS | win32service.SERVICE_START,
        )
        observed_before = int(win32service.QueryServiceStatus(service_handle)[1])
        if observed_before != before_state:
            before_state = observed_before

        running_state = int(win32service.SERVICE_RUNNING)
        if before_state == running_state:
            return {
                "mode": "remote_scm_service",
                "result": "already_running",
                "started": False,
                "before_state": before_state,
                "after_state": before_state,
            }

        win32service.StartService(service_handle, None)
        deadline = time.monotonic() + 20.0
        after_state = before_state
        while time.monotonic() < deadline:
            after_state = int(win32service.QueryServiceStatus(service_handle)[1])
            if after_state == running_state:
                return {
                    "mode": "remote_scm_service",
                    "result": "recovered",
                    "started": True,
                    "before_state": before_state,
                    "after_state": after_state,
                }
            time.sleep(0.5)
        raise RecoveryError(f"remote_scm_runner_not_running:{after_state}")
    except RecoveryError:
        raise
    except Exception as exc:
        code = getattr(exc, "winerror", None)
        if code is None and getattr(exc, "args", None):
            try:
                code = int(exc.args[0])
            except (TypeError, ValueError):
                code = None
        suffix = str(code) if code is not None else type(exc).__name__
        raise RecoveryError(f"remote_scm_failed:{suffix}") from exc
    finally:
        if service_handle is not None:
            try:
                win32service.CloseServiceHandle(service_handle)
            except Exception:
                pass
        if scm_handle is not None:
            try:
                win32service.CloseServiceHandle(scm_handle)
            except Exception:
                pass

def recover(correlation_id: str) -> dict[str, Any]:
    before = desktop_worker()
    refresh = {
        "performed": False,
        "expected_sha": EXPECTED_RUNTIME_SHA,
        "replayed": False,
    }

    if not before["runner_recovery_capability"]:
        if not before["runtime_refresh_capability"]:
            scm_result = recover_via_remote_scm()
            after = desktop_worker()
            return {
                "ok": True,
                "task_type": TASK_TYPE,
                "target_host": TARGET_HOST,
                "dispatch_worker_id": after["worker_id"],
                "worker_before": before,
                "worker_after": after,
                "runtime_refresh": refresh,
                "recovery_channel": "remote_scm",
                "handler_result": scm_result,
                "runner_recovery_replayed": False,
                "correlation_id": correlation_id,
                "production_touched": False,
                "secrets_read": False,
                "observed_at": now_iso(),
            }
        refresh_intake, refresh_result = enqueue_and_wait(
            REFRESH_TASK_TYPE,
            payload={
                "target_host": TARGET_HOST,
                "expected_sha": EXPECTED_RUNTIME_SHA,
                "worker_hint": "builder",
            },
            correlation_id=f"{correlation_id}-refresh",
            timeout_seconds=20.0,
        )
        if refresh_result.get("handler") != REFRESH_TASK_TYPE:
            raise RecoveryError("runtime_refresh_handler_mismatch")
        if str(refresh_result.get("host") or "").casefold() != TARGET_HOST.casefold():
            raise RecoveryError("runtime_refresh_host_mismatch")
        if str(refresh_result.get("expected_sha") or "") != EXPECTED_RUNTIME_SHA:
            raise RecoveryError("runtime_refresh_sha_mismatch")
        refresh = {
            "performed": True,
            "expected_sha": EXPECTED_RUNTIME_SHA,
            "replayed": refresh_intake.get("replayed") is True,
        }
        after_refresh = wait_for_refreshed_worker()
    else:
        after_refresh = before

    recovery_intake, result = enqueue_and_wait(
        TASK_TYPE,
        payload={"target_host": TARGET_HOST, "worker_hint": "builder"},
        correlation_id=f"{correlation_id}-runner",
        timeout_seconds=25.0,
    )
    if result.get("handler") != TASK_TYPE:
        raise RecoveryError("desktop_recovery_handler_mismatch")
    if str(result.get("host") or "").casefold() != TARGET_HOST.casefold():
        raise RecoveryError("desktop_recovery_host_mismatch")
    if str(result.get("worker_id") or "") != after_refresh["worker_id"]:
        raise RecoveryError("desktop_recovery_worker_mismatch")
    if result.get("result") not in {"recovered", "already_running"}:
        raise RecoveryError("desktop_recovery_unexpected_result")
    if result.get("mode") not in {"service", "scheduled_task"}:
        raise RecoveryError("desktop_recovery_mode_invalid")

    after = desktop_worker(require_runner_capability=True)
    return {
        "ok": True,
        "task_type": TASK_TYPE,
        "target_host": TARGET_HOST,
        "dispatch_worker_id": after["worker_id"],
        "worker_before": before,
        "worker_after_refresh": after_refresh,
        "worker_after": after,
        "runtime_refresh": refresh,
        "handler_result": {
            "mode": result.get("mode"),
            "result": result.get("result"),
            "started": result.get("started") is True,
            "before_state": result.get("before_state"),
            "after_state": result.get("after_state"),
        },
        "runner_recovery_replayed": recovery_intake.get("replayed") is True,
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
