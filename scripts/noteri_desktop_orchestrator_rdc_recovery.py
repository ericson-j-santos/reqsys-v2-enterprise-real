#!/usr/bin/env python3
"""Recuperação governada do Remote Desktop Commander via Orchestrator do Desktop."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time
import uuid
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
TARGET_WORKER = "desktop-pdqk954"
CONTROL_PLANE_PORT = 8787
TASK_TYPE = "host.rdc.recover.v1"
CONFIRM = "RECOVER-DESKTOP-RDC-VIA-ORCHESTRATOR"
EXPECTED_TASK = r"\Automation\RemoteDesktopCommander"
EXPECTED_LAUNCHER = r"C:\RemoteDesktopCommander\start-remote-desktop-commander.cmd"
TERMINAL = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}


class RecoveryError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_noteri(host: str | None = None, platform: str | None = None) -> None:
    observed_host = host or socket.gethostname()
    observed_platform = platform or os.name
    if observed_platform != "nt":
        raise RecoveryError("windows_required")
    if observed_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise RecoveryError("source_host_not_authorized")


def request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_seconds: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    method = str(method or "").upper()
    if method not in {"GET", "POST"}:
        raise RecoveryError("control_plane_method_not_allowlisted")
    if path not in {"/readyz", "/v1/status", "/v1/intake"} and not path.startswith(
        "/v1/work-items/"
    ):
        raise RecoveryError("control_plane_path_not_allowlisted")
    if method == "POST" and path != "/v1/intake":
        raise RecoveryError("control_plane_post_not_allowlisted")
    if method == "GET" and path == "/v1/intake":
        raise RecoveryError("control_plane_get_not_allowlisted")

    body = None
    headers = {"Accept": "application/json", "Cache-Control": "no-store"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"

    connection = HTTPConnection(
        TARGET_HOST,
        CONTROL_PLANE_PORT,
        timeout=max(1.0, min(timeout_seconds, 10.0)),
    )
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(262144).decode("utf-8", errors="replace")
    except (OSError, HTTPException, TimeoutError) as exc:
        raise RecoveryError("control_plane_unavailable") from exc
    finally:
        connection.close()

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise RecoveryError("control_plane_invalid_json") from exc
    if not isinstance(data, dict):
        raise RecoveryError("control_plane_invalid_payload")
    return int(response.status), data


def require_worker(requester=request_json) -> dict[str, Any]:
    ready_status, ready = requester("GET", "/readyz")
    if ready_status != 200 or ready.get("ready") is not True:
        raise RecoveryError("orchestrator_not_ready")

    status_code, status = requester("GET", "/v1/status")
    if status_code != 200:
        raise RecoveryError(f"orchestrator_status_http_{status_code}")
    workers_root = status.get("workers")
    workers = workers_root.get("workers") if isinstance(workers_root, dict) else None
    if not isinstance(workers, list):
        raise RecoveryError("worker_registry_invalid")
    matches = [
        worker
        for worker in workers
        if isinstance(worker, dict)
        and str(worker.get("worker_id") or "").casefold() == TARGET_WORKER.casefold()
        and str(worker.get("device_name") or "").casefold() == TARGET_HOST.casefold()
    ]
    if len(matches) != 1:
        raise RecoveryError("desktop_worker_not_unique")
    worker = matches[0]
    capabilities = worker.get("capabilities")
    safe_tasks = capabilities.get("safe_task_types") if isinstance(capabilities, dict) else None
    if (
        worker.get("fresh") is not True
        or worker.get("eligible") is not True
        or worker.get("controller_online") is not True
        or worker.get("auth_valid") is not True
        or str(worker.get("profile") or "").upper() != "NORMAL"
    ):
        raise RecoveryError("desktop_worker_not_operational")
    if not isinstance(safe_tasks, list) or TASK_TYPE not in safe_tasks:
        raise RecoveryError("desktop_rdc_recovery_capability_missing")
    return {
        "worker_id": worker.get("worker_id"),
        "controller_version": worker.get("controller_version"),
        "fresh": True,
        "eligible": True,
        "recovery_contract_version": (
            capabilities.get("recovery_contract_version")
            if isinstance(capabilities, dict)
            else None
        ),
    }


def negative_read_control(requester=request_json) -> bool:
    missing = str(uuid.uuid4())
    status, payload = requester("GET", f"/v1/work-items/{missing}")
    return status == 404 and payload.get("error") == "work_item_not_found"


def build_request(correlation_id: str) -> dict[str, Any]:
    digest = hashlib.sha256(
        f"{TASK_TYPE}|{TARGET_HOST}|force_restart=true|{correlation_id}".encode("utf-8")
    ).hexdigest()
    return {
        "event_id": f"evt-rdc-recovery-{digest[:32]}",
        "correlation_id": correlation_id,
        "idempotency_key": f"desktop-rdc-recovery:{digest}",
        "task_type": TASK_TYPE,
        "payload": {
            "target_host": TARGET_HOST,
            "force_restart": True,
            "worker_hint": "builder",
        },
        "risk": 2,
        "max_attempts": 1,
        "lease_seconds": 60,
    }


def validate_result(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("status") != "CONCLUÍDO":
        raise RecoveryError(
            f"rdc_recovery_terminal_{str(item.get('status') or 'unknown')[:40]}"
        )
    result = item.get("result")
    if not isinstance(result, dict):
        raise RecoveryError("rdc_recovery_result_missing")
    if result.get("handler") != TASK_TYPE:
        raise RecoveryError("rdc_recovery_handler_mismatch")
    if str(result.get("host") or "").casefold() != TARGET_HOST.casefold():
        raise RecoveryError("rdc_recovery_host_mismatch")
    if str(result.get("task") or "").casefold() != EXPECTED_TASK.casefold():
        raise RecoveryError("rdc_recovery_task_mismatch")
    if str(result.get("launcher") or "").casefold() != EXPECTED_LAUNCHER.casefold():
        raise RecoveryError("rdc_recovery_launcher_mismatch")
    if result.get("force_restart") is not True:
        raise RecoveryError("rdc_recovery_force_restart_not_applied")

    after = result.get("after")
    if not isinstance(after, dict) or after.get("enabled") is not True:
        raise RecoveryError("rdc_recovery_after_invalid")
    if str(after.get("launcher") or "").casefold() != EXPECTED_LAUNCHER.casefold():
        raise RecoveryError("rdc_recovery_after_launcher_mismatch")
    action_path = str(after.get("action_path") or "").casefold()
    if not action_path.endswith(r"\system32\cmd.exe"):
        raise RecoveryError("rdc_recovery_after_action_mismatch")
    running_instance = str(result.get("running_instance") or "").strip()
    if not running_instance:
        raise RecoveryError("rdc_recovery_running_instance_missing")

    return {
        "handler": TASK_TYPE,
        "host": TARGET_HOST,
        "task": EXPECTED_TASK,
        "launcher": EXPECTED_LAUNCHER,
        "force_restart": True,
        "stopped_for_restart": bool(result.get("stopped_for_restart")),
        "running_instance_present": True,
        "after_enabled": True,
        "after_state": after.get("state"),
        "last_task_result": after.get("last_task_result"),
    }


def recover(
    *,
    confirm: str,
    correlation_id: str,
    evidence_file: Path,
    timeout_seconds: float = 60.0,
    requester=request_json,
    source_host: str | None = None,
    platform: str | None = None,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    correlation = str(correlation_id or "").strip()
    if not 8 <= len(correlation) <= 128 or any(ch in correlation for ch in "\r\n"):
        raise RecoveryError("correlation_id_invalid")
    if timeout_seconds <= 0 or timeout_seconds > 90:
        raise RecoveryError("timeout_seconds_out_of_range")
    require_noteri(source_host, platform)

    worker_before = require_worker(requester)
    if not negative_read_control(requester):
        raise RecoveryError("negative_read_control_failed")

    body = build_request(correlation)
    status, intake = requester("POST", "/v1/intake", body)
    if status not in {200, 201}:
        raise RecoveryError(f"rdc_recovery_intake_http_{status}")
    item = intake.get("item")
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        raise RecoveryError("rdc_recovery_intake_invalid")
    item_id = item["id"]
    if intake.get("replayed") is not True:
        dispatch = intake.get("dispatch")
        if not isinstance(dispatch, dict):
            raise RecoveryError("rdc_recovery_not_dispatched")
        assigned = dispatch.get("worker")
        if (
            not isinstance(assigned, dict)
            or str(assigned.get("device_name") or "").casefold()
            != TARGET_HOST.casefold()
        ):
            raise RecoveryError("rdc_recovery_wrong_worker")

    deadline = time.monotonic() + timeout_seconds
    terminal: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        read_status, snapshot = requester("GET", f"/v1/work-items/{item_id}")
        observed = snapshot.get("item") if isinstance(snapshot, dict) else None
        if read_status != 200 or not isinstance(observed, dict):
            raise RecoveryError("rdc_recovery_readback_invalid")
        if str(observed.get("status") or "") in TERMINAL:
            terminal = observed
            break
        sleep_fn(0.5)
    if terminal is None:
        raise RecoveryError("rdc_recovery_timeout")
    validated = validate_result(terminal)

    replay_status, replay = requester("POST", "/v1/intake", body)
    replay_item = replay.get("item") if isinstance(replay, dict) else None
    if (
        replay_status != 200
        or replay.get("replayed") is not True
        or replay.get("dispatch") is not None
        or not isinstance(replay_item, dict)
        or replay_item.get("id") != item_id
    ):
        raise RecoveryError("rdc_recovery_replay_not_idempotent")

    verify_status, verify = requester("GET", f"/v1/work-items/{item_id}")
    verify_item = verify.get("item") if isinstance(verify, dict) else None
    if verify_status != 200 or not isinstance(verify_item, dict):
        raise RecoveryError("rdc_recovery_independent_readback_missing")
    validate_result(verify_item)
    worker_after = require_worker(requester)

    evidence = {
        "schema_version": "1",
        "ok": True,
        "result": "DESKTOP_RDC_RECOVERY_DISPATCH_VERIFIED",
        "generated_at": now_iso(),
        "correlation_id": correlation,
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "control_plane_port": CONTROL_PLANE_PORT,
        "task_type": TASK_TYPE,
        "work_item_id": item_id,
        "worker_before": worker_before,
        "worker_after": worker_after,
        "recovery": validated,
        "replay_idempotent": True,
        "negative_read_control": True,
        "independent_readback": True,
        "rdc_transport_online_proven": False,
        "remote_shell_used": False,
        "credentials_supplied": False,
        "secrets_read": False,
        "production_touched": False,
        "reboot_performed": False,
    }
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()
    try:
        evidence = recover(
            confirm=args.confirm,
            correlation_id=args.correlation_id,
            evidence_file=args.evidence_file.resolve(),
            timeout_seconds=args.timeout_seconds,
        )
    except (RecoveryError, OSError, ValueError) as exc:
        evidence = {
            "schema_version": "1",
            "ok": False,
            "result": "DESKTOP_RDC_RECOVERY_BLOCKED",
            "generated_at": now_iso(),
            "reason": str(exc)[:160],
            "correlation_id": str(args.correlation_id)[:128],
            "source_host": EXPECTED_SOURCE_HOST,
            "target_host": TARGET_HOST,
            "control_plane_port": CONTROL_PLANE_PORT,
            "task_type": TASK_TYPE,
            "rdc_transport_online_proven": False,
            "remote_shell_used": False,
            "credentials_supplied": False,
            "secrets_read": False,
            "production_touched": False,
            "reboot_performed": False,
        }
        args.evidence_file.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.resolve().write_text(
            json.dumps(evidence, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(evidence, sort_keys=True))
        return 2

    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
