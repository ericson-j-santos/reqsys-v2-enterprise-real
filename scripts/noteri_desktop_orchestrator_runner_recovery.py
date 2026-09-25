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
REFRESH_TASK_TYPE = "host.orchestrator.refresh.v1"
ORCHESTRATOR_SHA = "63d26ff024e9f782bdddb7e954a6e247c8ef13b7"
TARGET_HOST = "DESKTOP-PDQK954"
CONFIRM = "RECOVER-DESKTOP-RUNNER-VIA-ORCHESTRATOR"
COMPLETED_STATUS = "CONCLUÍDO"
TERMINAL_STATUSES = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}


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


def _worker_operational(worker: dict[str, Any]) -> bool:
    return (
        worker.get("fresh") is True
        and worker.get("controller_online") is True
        and worker.get("auth_valid") is True
    )


def _submit_task(
    *,
    task_type: str,
    payload: dict[str, Any],
    correlation_id: str,
    idempotency_suffix: str,
    deadline: float,
) -> dict[str, Any]:
    event_id = f"{correlation_id}:{idempotency_suffix}:event"
    idempotency_key = f"{correlation_id}:{idempotency_suffix}"
    status, created = _request(
        "POST",
        "/v1/intake",
        {
            "event_id": event_id,
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key,
            "task_type": task_type,
            "payload": payload,
            "risk": 1,
            "max_attempts": 1,
            "lease_seconds": 60,
        },
    )
    if status not in {200, 201}:
        raise RecoveryError(f"{idempotency_suffix}_intake_http_{status}")

    item = created.get("item") if isinstance(created, dict) else None
    if not isinstance(item, dict) or not item.get("id"):
        raise RecoveryError(f"{idempotency_suffix}_work_item_missing")
    item_id = str(item["id"])
    replayed = created.get("replayed") is True

    if not replayed:
        dispatch = created.get("dispatch")
        if not isinstance(dispatch, dict):
            raise RecoveryError(f"{idempotency_suffix}_work_item_not_dispatched")
        worker = dispatch.get("worker")
        if (
            not isinstance(worker, dict)
            or str(worker.get("worker_id") or "").casefold() != WORKER_ID
        ):
            raise RecoveryError(f"{idempotency_suffix}_dispatch_worker_mismatch")

    observed = item
    while time.monotonic() < deadline:
        _, current = _request("GET", f"/v1/work-items/{item_id}")
        candidate = current.get("item") if isinstance(current, dict) else None
        if isinstance(candidate, dict):
            observed = candidate
            current_status = str(candidate.get("status") or "").strip().upper()
            if current_status in TERMINAL_STATUSES:
                break
        time.sleep(1)

    final_status = str(observed.get("status") or "").strip().upper()
    if final_status != COMPLETED_STATUS:
        raise RecoveryError(
            f"{idempotency_suffix}_not_completed:{final_status or 'UNKNOWN'}"
        )

    result = observed.get("result")
    if not isinstance(result, dict):
        raise RecoveryError(f"{idempotency_suffix}_result_missing")
    if str(result.get("handler") or "") != task_type:
        raise RecoveryError(f"{idempotency_suffix}_handler_mismatch")

    return {
        "event_id": event_id,
        "idempotency_key": idempotency_key,
        "work_item_id": item_id,
        "replayed": replayed,
        "result": result,
    }


def _wait_for_runner_capability(deadline: float) -> dict[str, Any]:
    last_reason = "worker_not_observed"
    while time.monotonic() < deadline:
        try:
            worker = _desktop_worker()
        except RecoveryError as exc:
            last_reason = str(exc)
        else:
            if not _worker_operational(worker):
                last_reason = "worker_not_operational"
            elif TASK_TYPE in _safe_task_types(worker):
                return worker
            else:
                last_reason = "runner_capability_missing"
        time.sleep(2)
    raise RecoveryError(f"desktop_worker_refresh_not_observed:{last_reason}")


def recover(correlation_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    worker_before = _desktop_worker()
    if not _worker_operational(worker_before):
        raise RecoveryError("desktop_worker_not_operational")

    safe_types_before = _safe_task_types(worker_before)
    refresh_task: dict[str, Any] | None = None
    worker_for_recovery = worker_before

    if TASK_TYPE not in safe_types_before:
        if REFRESH_TASK_TYPE not in safe_types_before:
            raise RecoveryError(
                "desktop_worker_runtime_drift_unrecoverable:"
                "runner_and_refresh_capabilities_missing"
            )

        refresh_task = _submit_task(
            task_type=REFRESH_TASK_TYPE,
            payload={
                "target_host": TARGET_HOST,
                "expected_sha": ORCHESTRATOR_SHA,
            },
            correlation_id=f"{correlation_id}:runtime-refresh",
            idempotency_suffix="runtime-refresh",
            deadline=deadline,
        )
        refresh_result = refresh_task["result"]
        if str(refresh_result.get("expected_sha") or "").lower() != ORCHESTRATOR_SHA:
            raise RecoveryError("runtime_refresh_sha_mismatch")
        worker_for_recovery = _wait_for_runner_capability(deadline)

    if TASK_TYPE not in _safe_task_types(worker_for_recovery):
        raise RecoveryError("desktop_worker_capability_missing:host.github_runner.recover.v1")

    recovery_task = _submit_task(
        task_type=TASK_TYPE,
        payload={"target_host": TARGET_HOST},
        correlation_id=correlation_id,
        idempotency_suffix="runner-recovery",
        deadline=deadline,
    )

    worker_after = _desktop_worker()
    if not _worker_operational(worker_after):
        raise RecoveryError("desktop_worker_not_operational_after_recovery")
    if TASK_TYPE not in _safe_task_types(worker_after):
        raise RecoveryError("desktop_worker_capability_lost_after_recovery")

    return {
        "ok": True,
        "environment": "dev",
        "target_host": TARGET_HOST,
        "transport": "noteri_to_desktop_orchestrator_8787",
        "task_type": TASK_TYPE,
        "correlation_id": correlation_id,
        "event_id": recovery_task["event_id"],
        "idempotency_key": recovery_task["idempotency_key"],
        "work_item_id": recovery_task["work_item_id"],
        "final_status": COMPLETED_STATUS,
        "result": recovery_task["result"],
        "runtime_refresh": {
            "attempted": refresh_task is not None,
            "expected_sha": ORCHESTRATOR_SHA if refresh_task is not None else None,
            "replayed": refresh_task["replayed"] if refresh_task is not None else False,
        },
        "worker_before": {
            "fresh": worker_before.get("fresh") is True,
            "controller_online": worker_before.get("controller_online") is True,
            "auth_valid": worker_before.get("auth_valid") is True,
            "runner_recovery_capability": TASK_TYPE in safe_types_before,
            "runtime_refresh_capability": REFRESH_TASK_TYPE in safe_types_before,
        },
        "worker_after": {
            "fresh": worker_after.get("fresh") is True,
            "controller_online": worker_after.get("controller_online") is True,
            "auth_valid": worker_after.get("auth_valid") is True,
            "runner_recovery_capability": TASK_TYPE in _safe_task_types(worker_after),
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
