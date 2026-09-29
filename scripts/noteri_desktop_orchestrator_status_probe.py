#!/usr/bin/env python3
"""Read-only, fixed-target Desktop Orchestrator status probe executed from Noteri."""
from __future__ import annotations

import argparse
import json
import os
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
ENDPOINT = "http://DESKTOP-PDQK954:8787"
TARGET_WORKER = "desktop-pdqk954"
TARGET_RUNTIME_SHA = "313f5da4bb0ee9dd70937c238c7cfdf4e3514602"
REFRESH_TASK = "host.orchestrator.refresh.v1"
BOOTSTRAP_TASK = "host.github_runner.bootstrap.v1"
CONFIRM = "PROBE-DESKTOP-ORCHESTRATOR-STATUS"
RECOVERY_CORRELATION_PREFIX = "desktop-runner-orchestrator-"


class ProbeError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_noteri() -> None:
    if os.name != "nt":
        raise ProbeError("windows_required")
    if socket.gethostname().casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise ProbeError("source_host_mismatch")


def request_json(path: str, timeout_seconds: float) -> tuple[int | None, dict[str, Any]]:
    request = urllib.request.Request(
        ENDPOINT + path,
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(response.status)
            raw = response.read(1024 * 1024).decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), {}
    except (urllib.error.URLError, OSError):
        return None, {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return status, {}
    return status, payload if isinstance(payload, dict) else {}


def sanitize_last_error(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    # Keep the diagnostic reason while preventing local Windows paths from
    # becoming durable evidence.
    parts = []
    for token in text.split():
        if len(token) >= 3 and token[1:3] in {":\\", ":/"}:
            parts.append("<path>")
        else:
            parts.append(token)
    return " ".join(parts)[:240]


def latest_runner_recovery_blocker(status: dict[str, Any]) -> dict[str, Any] | None:
    blockers = status.get("blockers")
    if not isinstance(blockers, list):
        return None
    matches = [
        item for item in blockers
        if isinstance(item, dict)
        and str(item.get("correlation_id") or "").startswith(RECOVERY_CORRELATION_PREFIX)
    ]
    if not matches:
        return None
    item = matches[0]
    return {
        "work_item_id": str(item.get("id") or "") or None,
        "correlation_id": str(item.get("correlation_id") or "") or None,
        "attempts": item.get("attempts"),
        "last_error": sanitize_last_error(item.get("last_error")),
    }


def probe(*, confirm: str, correlation_id: str, timeout_seconds: float) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise ProbeError("confirmation_invalid")
    if not 8 <= len(correlation_id.strip()) <= 160:
        raise ProbeError("correlation_id_invalid")
    if timeout_seconds <= 0 or timeout_seconds > 10:
        raise ProbeError("timeout_invalid")
    require_noteri()

    ready_status, ready = request_json("/readyz", timeout_seconds)
    status_code, status = request_json("/v1/status", timeout_seconds)
    workers = status.get("workers", {}).get("workers", [])
    matches = [
        item for item in workers
        if isinstance(item, dict)
        and str(item.get("worker_id") or "").casefold() == TARGET_WORKER.casefold()
    ] if isinstance(workers, list) else []

    worker = matches[0] if len(matches) == 1 else {}
    capabilities = worker.get("capabilities") if isinstance(worker, dict) else {}
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    safe_tasks = capabilities.get("safe_task_types")
    safe_tasks = sorted(str(item) for item in safe_tasks if isinstance(item, str)) if isinstance(safe_tasks, list) else []
    runtime_source_sha = str(capabilities.get("runtime_source_sha") or "").strip().lower() or None
    worker_instance_id = str(capabilities.get("worker_instance_id") or "").strip().lower() or None
    recovery_blocker = latest_runner_recovery_blocker(status)

    return {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "ok": True,
        "probe_completed": True,
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "endpoint": ENDPOINT,
        "correlation_id": correlation_id,
        "ready_http_status": ready_status,
        "ready": bool(ready_status == 200 and ready.get("ready") is True),
        "status_http_status": status_code,
        "worker_match_count": len(matches),
        "worker_id": worker.get("worker_id"),
        "device_name": worker.get("device_name"),
        "fresh": worker.get("fresh"),
        "eligible": worker.get("eligible"),
        "controller_version": worker.get("controller_version"),
        "profile": worker.get("profile"),
        "recovery_contract_version": capabilities.get("recovery_contract_version"),
        "safe_task_types": safe_tasks,
        "runtime_source_sha": runtime_source_sha,
        "worker_instance_id": worker_instance_id,
        "refresh_capability_present": REFRESH_TASK in safe_tasks,
        "bootstrap_capability_present": BOOTSTRAP_TASK in safe_tasks,
        "target_runtime_sha": TARGET_RUNTIME_SHA,
        "runtime_identity_current": runtime_source_sha == TARGET_RUNTIME_SHA,
        "latest_runner_recovery_blocker": recovery_blocker,
        "production_touched": False,
        "secrets_read": False,
        "remote_shell_used": False,
        "credentials_supplied": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    args = parser.parse_args()
    try:
        payload = probe(
            confirm=args.confirm,
            correlation_id=args.correlation_id,
            timeout_seconds=args.timeout_seconds,
        )
        code = 0
    except (ProbeError, OSError, ValueError) as exc:
        payload = {
            "schema_version": "1",
            "generated_at_utc": now_iso(),
            "ok": False,
            "probe_completed": False,
            "source_host": EXPECTED_SOURCE_HOST,
            "target_host": TARGET_HOST,
            "endpoint": ENDPOINT,
            "correlation_id": args.correlation_id,
            "error_code": str(exc)[:160],
            "production_touched": False,
            "secrets_read": False,
            "remote_shell_used": False,
            "credentials_supplied": False,
        }
        code = 2
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
