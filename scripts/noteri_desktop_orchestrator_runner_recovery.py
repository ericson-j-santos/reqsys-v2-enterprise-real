#!/usr/bin/env python3
"""Recupera o GitHub runner do Desktop via Engineering Orchestrator, a partir do Noteri.

Contrato fechado:
- origem física: Noteri;
- destino único: DESKTOP-PDQK954:8787;
- task única: host.github_runner.recover.v1;
- sem shell, caminho, host, porta, URL ou task arbitrários.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time
import uuid
from datetime import UTC, datetime
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
CONTROL_PLANE_PORT = 8787
TASK_TYPE = "host.github_runner.recover.v1"
CONFIRM = "RECOVER-DESKTOP-GITHUB-RUNNER-VIA-ORCHESTRATOR"
TERMINAL = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}


class RecoveryError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def validate_source_host(
    host: str | None = None,
    platform: str | None = None,
) -> None:
    observed_host = host or socket.gethostname()
    observed_platform = platform or os.name
    if observed_platform != "nt":
        raise RecoveryError("windows_required")
    if observed_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise RecoveryError("source_host_not_authorized")


def normalize_correlation_id(value: str) -> str:
    correlation_id = str(value or "").strip()
    if not 8 <= len(correlation_id) <= 128:
        raise RecoveryError("correlation_id_invalid")
    if any(ch in correlation_id for ch in "\r\n"):
        raise RecoveryError("correlation_id_invalid")
    return correlation_id


def request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    if path not in {"/readyz", "/v1/workers", "/v1/intake"} and not path.startswith(
        "/v1/work-items/"
    ):
        raise RecoveryError("control_plane_path_not_allowlisted")
    normalized_method = str(method or "").strip().upper()
    if normalized_method not in {"GET", "POST"}:
        raise RecoveryError("control_plane_method_not_allowlisted")

    body = None
    headers = {"Accept": "application/json", "Cache-Control": "no-store"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"

    connection = HTTPConnection(TARGET_HOST, CONTROL_PLANE_PORT, timeout=timeout)
    try:
        connection.request(normalized_method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(262144).decode("utf-8", errors="replace")
        try:
            decoded = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise RecoveryError("control_plane_invalid_json") from exc
        if not isinstance(decoded, dict):
            raise RecoveryError("control_plane_invalid_payload")
        return int(response.status), decoded
    except (OSError, HTTPException, TimeoutError) as exc:
        raise RecoveryError("control_plane_unavailable") from exc
    finally:
        connection.close()


def require_ready(requester=request_json) -> None:
    status, payload = requester("GET", "/readyz")
    if status != 200 or payload.get("ready") is not True:
        raise RecoveryError("orchestrator_not_ready")


def require_desktop_worker(requester=request_json) -> dict[str, Any]:
    status, payload = requester("GET", "/v1/workers")
    workers = payload.get("workers") if isinstance(payload, dict) else None
    if status != 200 or not isinstance(workers, list):
        raise RecoveryError("worker_registry_invalid")
    matches = [
        worker
        for worker in workers
        if isinstance(worker, dict)
        and str(worker.get("device_name") or "").casefold() == TARGET_HOST.casefold()
    ]
    if len(matches) != 1:
        raise RecoveryError("desktop_worker_not_unique")
    worker = matches[0]
    capabilities = worker.get("capabilities") or {}
    safe_task_types = capabilities.get("safe_task_types") if isinstance(capabilities, dict) else None
    if (
        worker.get("fresh") is not True
        or worker.get("controller_online") is not True
        or worker.get("auth_valid") is not True
        or str(worker.get("profile") or "").upper() != "NORMAL"
    ):
        raise RecoveryError("desktop_worker_not_operational")
    if not isinstance(safe_task_types, list) or TASK_TYPE not in safe_task_types:
        raise RecoveryError("desktop_worker_recovery_capability_missing")
    return worker


def negative_read_control(requester=request_json) -> bool:
    missing_id = f"negative-{uuid.uuid4().hex}"
    status, payload = requester("GET", f"/v1/work-items/{missing_id}")
    return status == 404 and payload.get("error") == "work_item_not_found"


def build_request(correlation_id: str) -> dict[str, Any]:
    digest = hashlib.sha256(
        f"{TASK_TYPE}|{TARGET_HOST}|{correlation_id}".encode("utf-8")
    ).hexdigest()
    return {
        "event_id": f"evt-runner-recovery-{digest[:32]}",
        "correlation_id": correlation_id,
        "idempotency_key": f"desktop-runner-recovery:{digest}",
        "task_type": TASK_TYPE,
        "payload": {
            "target_host": TARGET_HOST,
            "worker_hint": "builder",
        },
        "risk": 2,
        "max_attempts": 1,
        "lease_seconds": 60,
    }


def validate_completed(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("status") != "CONCLUÍDO":
        raise RecoveryError(f"runner_recovery_terminal_{item.get('status') or 'unknown'}")
    result = item.get("result")
    if not isinstance(result, dict):
        raise RecoveryError("runner_recovery_result_missing")
    if result.get("handler") != TASK_TYPE:
        raise RecoveryError("runner_recovery_handler_mismatch")
    if str(result.get("host") or "").casefold() != TARGET_HOST.casefold():
        raise RecoveryError("runner_recovery_host_mismatch")
    if result.get("result") not in {"recovered", "already_running"}:
        raise RecoveryError("runner_recovery_result_invalid")
    return result


def recover(
    *,
    confirm: str,
    correlation_id: str,
    evidence_file: Path,
    requester=request_json,
    timeout_seconds: float = 75.0,
    source_host: str | None = None,
    platform: str | None = None,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    validate_source_host(source_host, platform)
    correlation = normalize_correlation_id(correlation_id)
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise RecoveryError("timeout_invalid")

    require_ready(requester)
    worker_before = require_desktop_worker(requester)
    if not negative_read_control(requester):
        raise RecoveryError("negative_read_control_failed")

    body = build_request(correlation)
    status, intake = requester("POST", "/v1/intake", body)
    if status not in {200, 201}:
        raise RecoveryError(f"runner_recovery_intake_http_{status}")
    item = intake.get("item")
    dispatch = intake.get("dispatch")
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        raise RecoveryError("runner_recovery_intake_invalid")
    if intake.get("replayed") is not True and not isinstance(dispatch, dict):
        raise RecoveryError("runner_recovery_not_dispatched")
    if isinstance(dispatch, dict):
        assigned = dispatch.get("worker") or {}
        if str(assigned.get("device_name") or "").casefold() != TARGET_HOST.casefold():
            raise RecoveryError("runner_recovery_dispatched_to_wrong_host")

    item_id = item["id"]
    deadline = time.monotonic() + timeout_seconds
    terminal: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        read_status, snapshot = requester("GET", f"/v1/work-items/{item_id}")
        observed = snapshot.get("item") if isinstance(snapshot, dict) else None
        if read_status != 200 or not isinstance(observed, dict):
            raise RecoveryError("runner_recovery_readback_invalid")
        state = str(observed.get("status") or "")
        if state in TERMINAL:
            terminal = observed
            break
        sleep_fn(0.5)
    if terminal is None:
        raise RecoveryError("runner_recovery_timeout")
    result = validate_completed(terminal)

    replay_status, replay = requester("POST", "/v1/intake", body)
    replay_item = replay.get("item") if isinstance(replay, dict) else None
    if (
        replay_status != 200
        or replay.get("replayed") is not True
        or replay.get("dispatch") is not None
        or not isinstance(replay_item, dict)
        or replay_item.get("id") != item_id
    ):
        raise RecoveryError("runner_recovery_replay_not_idempotent")

    verify_status, verified = requester("GET", f"/v1/work-items/{item_id}")
    verified_item = verified.get("item") if isinstance(verified, dict) else None
    if verify_status != 200 or not isinstance(verified_item, dict):
        raise RecoveryError("runner_recovery_independent_readback_missing")
    verify_result = validate_completed(verified_item)
    worker_after = require_desktop_worker(requester)

    evidence = {
        "schema_version": "1.0.0",
        "ok": True,
        "result": "DESKTOP_GITHUB_RUNNER_RECOVERY_COMPLETED",
        "generated_at": now_iso(),
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "control_plane_port": CONTROL_PLANE_PORT,
        "task_type": TASK_TYPE,
        "correlation_id": correlation,
        "work_item_id": item_id,
        "worker_id": worker_after.get("worker_id"),
        "worker_controller_version": worker_after.get("controller_version"),
        "worker_fresh_before": worker_before.get("fresh") is True,
        "worker_fresh_after": worker_after.get("fresh") is True,
        "recovery_mode": verify_result.get("mode"),
        "recovery_result": verify_result.get("result"),
        "replay_idempotent": True,
        "negative_read_control": True,
        "independent_readback": True,
        "remote_shell_used": False,
        "credentials_supplied": False,
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
    parser.add_argument("--timeout-seconds", type=float, default=75.0)
    args = parser.parse_args()
    evidence_path = args.evidence_file.resolve()
    try:
        result = recover(
            confirm=args.confirm,
            correlation_id=args.correlation_id,
            evidence_file=evidence_path,
            timeout_seconds=args.timeout_seconds,
        )
    except RecoveryError as exc:
        blocked = {
            "schema_version": "1.0.0",
            "ok": False,
            "result": "DESKTOP_GITHUB_RUNNER_RECOVERY_BLOCKED",
            "reason": str(exc)[:160],
            "source_host": EXPECTED_SOURCE_HOST,
            "target_host": TARGET_HOST,
            "control_plane_port": CONTROL_PLANE_PORT,
            "task_type": TASK_TYPE,
            "correlation_id": str(args.correlation_id)[:128],
            "remote_shell_used": False,
            "credentials_supplied": False,
            "secrets_read": False,
            "production_touched": False,
            "reboot_performed": False,
        }
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(blocked, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(blocked, ensure_ascii=True, sort_keys=True))
        return 2

    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
