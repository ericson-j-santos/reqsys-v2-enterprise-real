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

from scripts.install_windows_autostart import install, start_supervisor

EXPECTED_HOST = "DESKTOP-PDQK954"
INSTALL_ROOT = Path(r"C:\dev\chatgpt-workers\reqsys-orchestrator-24x7-runtime")
ENDPOINT = "http://127.0.0.1:8787"
WORKER_ID = "desktop-pdqk954"
CONTROLLER_VERSION = "0.2.51"
CONFIRM = "RECOVER-PC24X7-ORCHESTRATOR-DEV"
DEFAULT_TIMEOUT_SECONDS = 60.0


class RecoveryError(RuntimeError):
    pass


def require_target(*, host: str | None = None, platform: str | None = None) -> None:
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_host.casefold() != EXPECTED_HOST.casefold():
        raise RecoveryError("host_not_authorized")
    if actual_platform != "nt":
        raise RecoveryError("windows_required")


def get_json(path: str, timeout: float = 4.0) -> tuple[int | None, Any]:
    request = urllib.request.Request(
        ENDPOINT + path,
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


def runtime_state(
    get_json_fn: Callable[[str], tuple[int | None, Any]] = get_json,
) -> dict[str, Any]:
    ready_status, ready_payload = get_json_fn("/readyz")
    workers_status, workers_payload = get_json_fn("/v1/workers")
    workers = workers_payload.get("workers") if isinstance(workers_payload, dict) else None
    desktop_matches = []
    if isinstance(workers, list):
        desktop_matches = [
            item
            for item in workers
            if isinstance(item, dict)
            and str(item.get("worker_id") or "").casefold() == WORKER_ID
        ]
    desktop = None
    if len(desktop_matches) == 1:
        item = desktop_matches[0]
        desktop = {
            "fresh": item.get("fresh") is True,
            "controller_online": item.get("controller_online") is True,
            "auth_valid": item.get("auth_valid") is True,
            "profile": str(item.get("profile") or "").strip().upper(),
        }
    ready = (
        ready_status == 200
        and isinstance(ready_payload, dict)
        and ready_payload.get("ready") is True
    )
    worker_operational = bool(
        desktop
        and desktop["fresh"]
        and desktop["controller_online"]
        and desktop["auth_valid"]
        and desktop["profile"] in {"NORMAL", "ESTUDO"}
    )
    return {
        "ready": ready,
        "ready_http_status": ready_status,
        "workers_http_status": workers_status,
        "desktop_match_count": len(desktop_matches) if isinstance(workers, list) else None,
        "desktop": desktop,
        "worker_operational": worker_operational,
    }


def recover(
    *,
    confirm: str,
    source_root: Path,
    evidence_path: Path,
    host: str | None = None,
    platform: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    install_fn=install,
    start_fn=start_supervisor,
    state_fn: Callable[[], dict[str, Any]] = runtime_state,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    require_target(host=host, platform=platform)
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise RecoveryError("timeout_invalid")

    source = source_root.resolve()
    if not (source / "orchestrator" / "__init__.py").is_file():
        raise RecoveryError("source_contract_invalid")
    if not (source / "scripts" / "service_supervisor.py").is_file():
        raise RecoveryError("source_contract_invalid")

    before = state_fn()
    installed = install_fn(
        source_root=source,
        install_root=INSTALL_ROOT,
        mode="control-plane-worker",
        endpoint=ENDPOINT,
        worker_id=WORKER_ID,
        controller_version=CONTROLLER_VERSION,
        dispatch_priority=10,
        port=8787,
        startup_root=None,
    )
    if str(installed.get("mode") or "") != "control-plane-worker":
        raise RecoveryError("install_contract_invalid")

    pid = start_fn(
        Path(installed["install_root"]),
        Path(installed["supervisor_config"]),
    )
    if not isinstance(pid, int) or pid <= 0:
        raise RecoveryError("supervisor_start_failed")

    deadline = time.monotonic() + timeout_seconds
    after = state_fn()
    while time.monotonic() < deadline:
        after = state_fn()
        if after.get("ready") is True and after.get("worker_operational") is True:
            break
        sleep_fn(2.0)

    if after.get("ready") is not True:
        raise RecoveryError("readiness_timeout")
    if after.get("worker_operational") is not True:
        raise RecoveryError("desktop_worker_not_operational")

    payload = {
        "ok": True,
        "environment": "dev",
        "host": EXPECTED_HOST,
        "source_contract_validated": True,
        "runtime_reinstalled": True,
        "supervisor_pid_present": True,
        "before": before,
        "after": after,
        "production_touched": False,
        "secrets_read": False,
        "task_created_or_modified": False,
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--evidence-path", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()
    try:
        result = recover(
            confirm=args.confirm,
            source_root=args.source_root,
            evidence_path=args.evidence_path,
            timeout_seconds=args.timeout_seconds,
        )
    except (RecoveryError, OSError, ValueError) as exc:
        blocked = {
            "ok": False,
            "environment": "dev",
            "host": EXPECTED_HOST,
            "error_code": str(exc),
            "production_touched": False,
            "secrets_read": False,
            "task_created_or_modified": False,
        }
        args.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_path.write_text(
            json.dumps(blocked, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(blocked, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
