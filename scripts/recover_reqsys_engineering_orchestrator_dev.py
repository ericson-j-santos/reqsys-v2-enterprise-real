#!/usr/bin/env python3
"""Recupera e valida o ReqSys Engineering Orchestrator DEV no Desktop PC24x7."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

EXPECTED_HOST = "DESKTOP-PDQK954"
CONTROL_PLANE = "http://127.0.0.1:8787"
TASK_NAME = r"\Automation\ReqSysOrchestrator24x7"
ORCHESTRATOR_INSTALL_ROOT = Path(
    r"C:\dev\chatgpt-workers\reqsys-orchestrator-24x7-runtime"
)
CONFIRM = "RECOVER-REQSYS-ENGINEERING-ORCHESTRATOR-DEV"
DEFAULT_TIMEOUT_SECONDS = 60.0
TASK_GRACE_ATTEMPTS = 6
POLL_SECONDS = 2.0
RUNNER_TRACKING_ENV = "RUNNER_TRACKING_ID"


class RecoveryError(RuntimeError):
    pass


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def require_target(*, host: str | None = None, platform: str | None = None) -> None:
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_host.casefold() != EXPECTED_HOST.casefold():
        raise RecoveryError("host_not_authorized")
    if actual_platform != "nt":
        raise RecoveryError("windows_required")


def _get_json(path: str, timeout: float = 4.0) -> tuple[int | None, Any]:
    request = urllib.request.Request(
        CONTROL_PLANE + path,
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), None
    except (urllib.error.URLError, OSError):
        return None, None

    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, None


def probe_ready() -> bool:
    status, payload = _get_json("/readyz")
    if status != 200:
        return False
    return isinstance(payload, dict) and payload.get("ready") is True


def probe_noteri_worker() -> dict[str, Any]:
    status, payload = _get_json("/v1/workers")
    workers = payload.get("workers") if isinstance(payload, dict) else None
    if status != 200 or not isinstance(workers, list):
        return {
            "reachable": status is not None,
            "http_status": status,
            "payload_valid": False,
            "match_count": None,
            "operational": False,
        }

    matches = [
        item
        for item in workers
        if isinstance(item, dict)
        and str(item.get("device_name") or "").casefold() == "noteri"
    ]
    result: dict[str, Any] = {
        "reachable": True,
        "http_status": 200,
        "payload_valid": True,
        "match_count": len(matches),
        "operational": False,
    }
    if len(matches) == 1:
        worker = matches[0]
        snapshot = {
            "fresh": worker.get("fresh") is True,
            "controller_online": worker.get("controller_online") is True,
            "auth_valid": worker.get("auth_valid") is True,
            "profile": str(worker.get("profile") or "").strip().upper(),
        }
        snapshot["operational"] = (
            snapshot["fresh"]
            and snapshot["controller_online"]
            and snapshot["auth_valid"]
            and snapshot["profile"] in {"NORMAL", "ESTUDO"}
        )
        result["noteri"] = snapshot
        result["operational"] = snapshot["operational"]
    return result


def run_existing_task() -> int:
    system_root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    executable = system_root / "System32" / "schtasks.exe"
    if not executable.is_file():
        raise RecoveryError("schtasks_unavailable")
    completed = subprocess.run(
        [str(executable), "/Run", "/TN", TASK_NAME],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=20,
        check=False,
    )
    return int(completed.returncode)


def validate_runtime_layout(runtime_root: Path) -> dict[str, Any]:
    root = runtime_root.resolve()
    service_config = root / "service-config.json"
    worker_config = root / "worker-config.json"
    supervisor = root / "scripts" / "service_supervisor.py"
    package = root / "orchestrator" / "__init__.py"
    for required in (service_config, worker_config, supervisor, package):
        if not required.is_file():
            raise RecoveryError("orchestrator_runtime_incomplete")

    try:
        service = json.loads(service_config.read_text(encoding="utf-8"))
        worker = json.loads(worker_config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryError("orchestrator_runtime_config_invalid") from exc

    expected_ready = CONTROL_PLANE + "/readyz"
    checks = (
        service.get("mode") == "control-plane-worker",
        Path(str(service.get("install_root") or "")).resolve() == root,
        int(service.get("port") or 0) == 8787,
        str(service.get("ready_url") or "").rstrip("/") == expected_ready,
        Path(str(service.get("worker_config") or "")).resolve() == worker_config.resolve(),
        str(worker.get("endpoint") or "").rstrip("/") == CONTROL_PLANE,
        str(worker.get("worker_id") or "").casefold() == "desktop-pdqk954",
    )
    if not all(checks):
        raise RecoveryError("orchestrator_runtime_contract_invalid")

    return {
        "root": root,
        "service_config": service_config.resolve(),
    }


def start_validated_supervisor(
    runtime_root: Path = ORCHESTRATOR_INSTALL_ROOT,
) -> dict[str, Any]:
    layout = validate_runtime_layout(runtime_root)
    root = Path(layout["root"])
    service_config = Path(layout["service_config"])
    log_path = root / "logs" / "study-mode-supervisor-recovery.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    tracking_removed = env.pop(RUNNER_TRACKING_ENV, None) is not None
    log_handle = log_path.open("ab", buffering=0)
    kwargs: dict[str, Any] = {
        "cwd": str(root),
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "env": env,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True

    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "scripts.service_supervisor",
                "--config",
                str(service_config),
            ],
            **kwargs,
        )
    except OSError as exc:
        log_handle.close()
        raise RecoveryError("orchestrator_supervisor_start_failed") from exc

    return {
        "started": process.pid > 0,
        "pid_present": process.pid > 0,
        "tracking_marker_removed": tracking_removed,
        "runtime_contract_validated": True,
    }


def _observe(
    *,
    ready_probe: Callable[[], bool],
    worker_probe: Callable[[], dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    ready = bool(ready_probe())
    worker = worker_probe()
    return ready, worker


def recover(
    *,
    confirm: str,
    evidence_path: Path,
    host: str | None = None,
    platform: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ready_probe: Callable[[], bool] = probe_ready,
    worker_probe: Callable[[], dict[str, Any]] = probe_noteri_worker,
    task_runner: Callable[[], int] = run_existing_task,
    supervisor_starter: Callable[[], dict[str, Any]] = start_validated_supervisor,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    require_target(host=host, platform=platform)
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise RecoveryError("timeout_invalid")

    recovery_attempted = False
    supervisor_fallback_used = False
    supervisor_start: dict[str, Any] | None = None
    ready_before, worker_before = _observe(
        ready_probe=ready_probe,
        worker_probe=worker_probe,
    )
    ready_after = ready_before
    worker_after = worker_before

    if not ready_before:
        recovery_attempted = True
        if task_runner() != 0:
            raise RecoveryError("orchestrator_task_start_failed")

        for _ in range(TASK_GRACE_ATTEMPTS):
            ready_after, worker_after = _observe(
                ready_probe=ready_probe,
                worker_probe=worker_probe,
            )
            if ready_after:
                break
            sleep_fn(POLL_SECONDS)

        if not ready_after:
            supervisor_fallback_used = True
            supervisor_start = supervisor_starter()
            if supervisor_start.get("started") is not True:
                raise RecoveryError("orchestrator_supervisor_start_failed")

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        ready_after, worker_after = _observe(
            ready_probe=ready_probe,
            worker_probe=worker_probe,
        )
        if ready_after and worker_after.get("operational") is True:
            break
        sleep_fn(POLL_SECONDS)

    if not ready_after:
        raise RecoveryError("orchestrator_readiness_timeout")
    if worker_after.get("operational") is not True:
        raise RecoveryError("noteri_worker_not_operational")

    if not recovery_attempted:
        recovery_method = "not_required"
    elif supervisor_fallback_used:
        recovery_method = "scheduled_task_then_validated_supervisor"
    else:
        recovery_method = "existing_scheduled_task"

    payload = {
        "ok": True,
        "environment": "dev",
        "host": EXPECTED_HOST,
        "control_plane_ready": True,
        "noteri_worker": worker_after,
        "recovery_attempted": recovery_attempted,
        "recovery_method": recovery_method,
        "scheduled_task": TASK_NAME,
        "supervisor_fallback_used": supervisor_fallback_used,
        "supervisor_start": supervisor_start,
        "task_created_or_modified": False,
        "production_touched": False,
        "secrets_read": False,
    }
    _write_evidence(evidence_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--evidence-path", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    try:
        result = recover(
            confirm=args.confirm,
            evidence_path=args.evidence_path.resolve(),
            timeout_seconds=args.timeout_seconds,
        )
    except (RecoveryError, OSError, subprocess.SubprocessError) as exc:
        blocked = {
            "ok": False,
            "environment": "dev",
            "host": EXPECTED_HOST,
            "error_code": str(exc),
            "task_created_or_modified": False,
            "production_touched": False,
            "secrets_read": False,
        }
        _write_evidence(args.evidence_path.resolve(), blocked)
        print(json.dumps(blocked, sort_keys=True))
        return 2

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
