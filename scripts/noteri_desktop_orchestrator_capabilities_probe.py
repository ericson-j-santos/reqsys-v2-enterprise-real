#!/usr/bin/env python3
"""Probe somente leitura das capabilities do Engineering Orchestrator no Desktop."""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
TARGET_WORKER = "desktop-pdqk954"
CONTROL_PLANE_PORT = 8787
CONFIRM = "PROBE-DESKTOP-ORCHESTRATOR-CAPABILITIES"
RUNTIME_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
WORKER_INSTANCE_RE = re.compile(r"^[0-9a-f]{32}$")
ALLOWED_PATHS = {"/readyz", "/v1/status"}
INTERESTING_TASKS = (
    "host.inventory.files.v1",
    "host.orchestrator.refresh.v1",
    "host.github_runner.recover.v1",
    "host.github_runner.bootstrap.v1",
    "host.rdc.recover.v1",
)


class ProbeError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_noteri(host: str | None = None, platform: str | None = None) -> None:
    observed_host = host or socket.gethostname()
    observed_platform = platform or os.name
    if observed_platform != "nt":
        raise ProbeError("windows_required")
    if observed_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise ProbeError("source_host_not_authorized")


def request_json(
    path: str,
    *,
    timeout_seconds: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    if path not in ALLOWED_PATHS:
        raise ProbeError("control_plane_path_not_allowlisted")
    connection = HTTPConnection(
        TARGET_HOST,
        CONTROL_PLANE_PORT,
        timeout=max(1.0, min(timeout_seconds, 10.0)),
    )
    try:
        connection.request(
            "GET",
            path,
            headers={"Accept": "application/json", "Cache-Control": "no-store"},
        )
        response = connection.getresponse()
        raw = response.read(262144).decode("utf-8", errors="replace")
    except (OSError, HTTPException, TimeoutError) as exc:
        raise ProbeError("control_plane_unavailable") from exc
    finally:
        connection.close()

    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise ProbeError("control_plane_invalid_json") from exc
    if not isinstance(payload, dict):
        raise ProbeError("control_plane_invalid_payload")
    return int(response.status), payload


def extract_worker(status_payload: dict[str, Any]) -> dict[str, Any]:
    workers_root = status_payload.get("workers")
    workers = workers_root.get("workers") if isinstance(workers_root, dict) else None
    if not isinstance(workers, list):
        raise ProbeError("worker_registry_invalid")

    matches = [
        worker
        for worker in workers
        if isinstance(worker, dict)
        and str(worker.get("worker_id") or "").casefold() == TARGET_WORKER.casefold()
        and str(worker.get("device_name") or "").casefold() == TARGET_HOST.casefold()
    ]
    if len(matches) != 1:
        raise ProbeError("desktop_worker_not_unique")

    worker = matches[0]
    capabilities = worker.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ProbeError("desktop_capabilities_invalid")
    safe_tasks = capabilities.get("safe_task_types")
    if not isinstance(safe_tasks, list) or any(not isinstance(item, str) for item in safe_tasks):
        raise ProbeError("desktop_safe_task_types_invalid")

    runtime_source_sha = str(capabilities.get("runtime_source_sha") or "").strip().lower()
    if runtime_source_sha and not RUNTIME_SHA_RE.fullmatch(runtime_source_sha):
        raise ProbeError("desktop_runtime_source_sha_invalid")

    worker_instance_id = str(capabilities.get("worker_instance_id") or "").strip().lower()
    if worker_instance_id and not WORKER_INSTANCE_RE.fullmatch(worker_instance_id):
        raise ProbeError("desktop_worker_instance_id_invalid")

    safe_set = set(safe_tasks)
    return {
        "worker_id": str(worker.get("worker_id") or ""),
        "device_name": str(worker.get("device_name") or ""),
        "controller_version": str(worker.get("controller_version") or ""),
        "fresh": worker.get("fresh") is True,
        "eligible": worker.get("eligible") is True,
        "controller_online": worker.get("controller_online"),
        "auth_valid": worker.get("auth_valid"),
        "profile": str(worker.get("profile") or ""),
        "recovery_contract_version": capabilities.get("recovery_contract_version"),
        "runtime_source_sha": runtime_source_sha or None,
        "worker_instance_id": worker_instance_id or None,
        "safe_task_types": sorted(safe_set),
        "interesting_capabilities": {
            task: task in safe_set for task in INTERESTING_TASKS
        },
    }


def probe(
    *,
    confirm: str,
    correlation_id: str,
    timeout_seconds: float,
    requester=request_json,
    source_host: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise ProbeError("confirmation_invalid")
    if not 8 <= len(str(correlation_id or "").strip()) <= 128:
        raise ProbeError("correlation_id_invalid")
    if timeout_seconds <= 0 or timeout_seconds > 10:
        raise ProbeError("timeout_seconds_out_of_range")
    require_noteri(source_host, platform)

    ready_status, ready = requester("/readyz", timeout_seconds=timeout_seconds)
    if ready_status != 200 or ready.get("ready") is not True:
        raise ProbeError("orchestrator_not_ready")

    status_code, status = requester("/v1/status", timeout_seconds=timeout_seconds)
    if status_code != 200:
        raise ProbeError(f"orchestrator_status_http_{status_code}")
    worker = extract_worker(status)

    return {
        "schema_version": "1",
        "ok": True,
        "result": "DESKTOP_ORCHESTRATOR_CAPABILITIES_OBSERVED",
        "generated_at": now_iso(),
        "correlation_id": correlation_id,
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "control_plane_port": CONTROL_PLANE_PORT,
        "ready": True,
        "worker": worker,
        "read_only": True,
        "http_methods_used": ["GET"],
        "remote_shell_used": False,
        "credentials_supplied": False,
        "secrets_read": False,
        "production_touched": False,
        "reboot_performed": False,
    }


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    args = parser.parse_args()

    try:
        evidence = probe(
            confirm=args.confirm,
            correlation_id=args.correlation_id,
            timeout_seconds=args.timeout_seconds,
        )
    except (ProbeError, OSError, ValueError) as exc:
        evidence = {
            "schema_version": "1",
            "ok": False,
            "result": "DESKTOP_ORCHESTRATOR_CAPABILITIES_BLOCKED",
            "generated_at": now_iso(),
            "reason": str(exc)[:160],
            "correlation_id": str(args.correlation_id)[:128],
            "source_host": EXPECTED_SOURCE_HOST,
            "target_host": TARGET_HOST,
            "control_plane_port": CONTROL_PLANE_PORT,
            "read_only": True,
            "http_methods_used": ["GET"],
            "remote_shell_used": False,
            "credentials_supplied": False,
            "secrets_read": False,
            "production_touched": False,
            "reboot_performed": False,
        }
        write_evidence(args.evidence_file.resolve(), evidence)
        print(json.dumps(evidence, sort_keys=True))
        return 2

    write_evidence(args.evidence_file.resolve(), evidence)
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
