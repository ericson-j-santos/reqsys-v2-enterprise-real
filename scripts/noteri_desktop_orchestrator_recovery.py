#!/usr/bin/env python3
"""Recupera o plano de controle Desktop via Engineering Orchestrator governado."""
from __future__ import annotations

import argparse
import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
CONTROL_PLANE = "http://DESKTOP-PDQK954:8787"
CONFIRM = "RECOVER-DESKTOP-CONTROL-VIA-ORCHESTRATOR"
RUNNER_RECOVERY_TASK = "host.github_runner.recover.v1"
RDC_RECOVERY_TASK = "host.rdc.recover.v1"
TERMINAL_STATUSES = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}


class RecoveryError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_noteri(host: str | None = None, platform: str | None = None) -> None:
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise RecoveryError("source_host_not_authorized")
    if actual_platform != "nt":
        raise RecoveryError("windows_required")


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int | None, dict[str, Any] | None]:
    raw = None
    headers = {"Accept": "application/json", "Cache-Control": "no-store"}
    if payload is not None:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(CONTROL_PLANE + path, data=raw, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5.0) as response:
            body = response.read().decode("utf-8")
            return int(response.status), json.loads(body)
    except urllib.error.HTTPError as exc:
        try:
            return int(exc.code), json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return int(exc.code), None
    except (urllib.error.URLError, OSError):
        return None, None


def desktop_worker_snapshot() -> dict[str, Any]:
    ready_status, ready = request_json("GET", "/readyz")
    workers_status, registry = request_json("GET", "/v1/workers")
    if ready_status != 200 or not isinstance(ready, dict) or ready.get("ready") is not True:
        raise RecoveryError("orchestrator_not_ready")
    workers = registry.get("workers") if isinstance(registry, dict) else None
    if workers_status != 200 or not isinstance(workers, list):
        raise RecoveryError("worker_registry_unavailable")
    matches = [
        item for item in workers
        if isinstance(item, dict)
        and str(item.get("device_name") or "").casefold() == TARGET_HOST.casefold()
    ]
    if len(matches) != 1:
        raise RecoveryError("desktop_worker_match_count_invalid")
    worker = matches[0]
    capabilities = worker.get("capabilities") if isinstance(worker.get("capabilities"), dict) else {}
    safe_types = capabilities.get("safe_task_types")
    if not isinstance(safe_types, list):
        safe_types = []
    snapshot = {
        "fresh": worker.get("fresh") is True,
        "controller_online": worker.get("controller_online") is True,
        "auth_valid": worker.get("auth_valid") is True,
        "eligible": worker.get("eligible") is True,
        "profile": str(worker.get("profile") or "").strip().upper(),
        "runner_recovery_capable": RUNNER_RECOVERY_TASK in safe_types,
        "rdc_recovery_capable": RDC_RECOVERY_TASK in safe_types,
    }
    if not all(snapshot[key] for key in ("fresh", "controller_online", "auth_valid", "eligible")):
        raise RecoveryError("desktop_worker_not_operational")
    return snapshot


def choose_task(worker: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if worker.get("runner_recovery_capable") is True:
        return RUNNER_RECOVERY_TASK, {"target_host": TARGET_HOST}
    if worker.get("rdc_recovery_capable") is True:
        return RDC_RECOVERY_TASK, {"target_host": TARGET_HOST, "force_restart": True}
    raise RecoveryError("no_supported_desktop_recovery_capability")


def recover(*, confirm: str, operation_id: str, correlation_id: str, evidence_file: Path, sleep_fn=time.sleep) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    require_noteri()
    op = operation_id.strip()
    corr = correlation_id.strip()
    if not op or len(op) > 80 or not corr or len(corr) > 160:
        raise RecoveryError("operation_identity_invalid")

    worker = desktop_worker_snapshot()
    task_type, task_payload = choose_task(worker)
    intake = {
        "event_id": f"evt-desktop-control-recovery-{op}",
        "correlation_id": corr,
        "idempotency_key": f"desktop-control-recovery:{op}",
        "task_type": task_type,
        "payload": task_payload,
        "risk": 1,
        "max_attempts": 1,
        "lease_seconds": 60,
    }
    status, response = request_json("POST", "/v1/intake", intake)
    if status not in (200, 201) or not isinstance(response, dict):
        raise RecoveryError("recovery_intake_failed")
    item = response.get("item")
    if not isinstance(item, dict) or not str(item.get("id") or ""):
        raise RecoveryError("recovery_item_missing")
    item_id = str(item["id"])

    deadline = time.monotonic() + 45.0
    observed: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        item_status, body = request_json("GET", f"/v1/work-items/{item_id}")
        current = body.get("item") if item_status == 200 and isinstance(body, dict) else None
        if isinstance(current, dict):
            observed = current
            if str(current.get("status") or "") in TERMINAL_STATUSES:
                break
        sleep_fn(2.0)

    if not isinstance(observed, dict):
        raise RecoveryError("recovery_readback_missing")
    final_status = str(observed.get("status") or "")
    result = observed.get("result") if isinstance(observed.get("result"), dict) else {}
    if final_status != "CONCLUÍDO":
        raise RecoveryError("recovery_task_not_completed")
    if result.get("handler") != task_type:
        raise RecoveryError("recovery_handler_mismatch")
    if str(result.get("host") or "").casefold() != TARGET_HOST.casefold():
        raise RecoveryError("recovery_target_readback_mismatch")

    payload = {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "ok": True,
        "result": "DESKTOP_CONTROL_RECOVERY_COMPLETED",
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "selected_task": task_type,
        "worker_before": worker,
        "intake_created": response.get("created") is True,
        "intake_replayed": response.get("replayed") is True,
        "final_status": final_status,
        "handler_confirmed": True,
        "recovery_result": str(result.get("result") or "executed")[:80],
        "force_restart": bool(result.get("force_restart")) if task_type == RDC_RECOVERY_TASK else False,
        "production_touched": False,
        "secrets_read": False,
        "credentials_supplied": False,
        "arbitrary_command_enabled": False,
    }
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        recover(
            confirm=args.confirm,
            operation_id=args.operation_id,
            correlation_id=args.correlation_id,
            evidence_file=args.evidence_file.resolve(),
        )
        return 0
    except (RecoveryError, OSError, ValueError) as exc:
        blocked = {
            "schema_version": "1",
            "generated_at_utc": now_iso(),
            "ok": False,
            "result": "DESKTOP_CONTROL_ORCHESTRATOR_RECOVERY_BLOCKED",
            "error_code": str(exc)[:160],
            "source_host": EXPECTED_SOURCE_HOST,
            "target_host": TARGET_HOST,
            "production_touched": False,
            "secrets_read": False,
            "credentials_supplied": False,
            "arbitrary_command_enabled": False,
        }
        args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.write_text(json.dumps(blocked, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(blocked, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
