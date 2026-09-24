from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from scripts.install_windows_autostart import install, start_supervisor

EXPECTED_HOST = "Noteri"
CONTROL_PLANE = "http://DESKTOP-PDQK954:8787"
INSTALL_ROOT = Path(r"C:\dev\chatgpt-workers\reqsys-orchestrator-24x7-runtime")
WORKER_ID = "noteri"
CONTROLLER_VERSION = "0.2.52"
PROFILE_TASK = "host.profile.set.v1"
CONFIRM = "RECOVER-NOTERI-ORCHESTRATOR-WORKER-DEV"
DEFAULT_TIMEOUT_SECONDS = 60.0


class RecoveryError(RuntimeError):
    pass


def _write_json(path: Path, payload: dict[str, Any]) -> None:
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


def source_sha(source_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    value = completed.stdout.strip().lower()
    if completed.returncode != 0 or len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise RecoveryError("source_sha_unavailable")
    return value


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


def worker_state(
    get_json_fn: Callable[[str], tuple[int | None, Any]] = _get_json,
) -> dict[str, Any]:
    status, payload = get_json_fn("/v1/workers")
    workers = payload.get("workers") if isinstance(payload, dict) else None
    if status != 200 or not isinstance(workers, list):
        return {
            "reachable": status is not None,
            "http_status": status,
            "payload_valid": False,
            "match_count": None,
            "operational": False,
            "profile_task_capable": False,
        }

    matches = [
        item
        for item in workers
        if isinstance(item, dict)
        and str(item.get("worker_id") or "").casefold() == WORKER_ID
        and str(item.get("device_name") or "").casefold() == EXPECTED_HOST.casefold()
    ]
    result: dict[str, Any] = {
        "reachable": True,
        "http_status": 200,
        "payload_valid": True,
        "match_count": len(matches),
        "operational": False,
        "profile_task_capable": False,
    }
    if len(matches) != 1:
        return result

    worker = matches[0]
    capabilities = worker.get("capabilities")
    safe_task_types = (
        capabilities.get("safe_task_types", [])
        if isinstance(capabilities, dict)
        else []
    )
    profile = str(worker.get("profile") or "").strip().upper()
    snapshot = {
        "fresh": worker.get("fresh") is True,
        "controller_online": worker.get("controller_online") is True,
        "auth_valid": worker.get("auth_valid") is True,
        "profile": profile,
    }
    capable = isinstance(safe_task_types, list) and PROFILE_TASK in safe_task_types
    operational = (
        snapshot["fresh"]
        and snapshot["controller_online"]
        and snapshot["auth_valid"]
        and profile in {"NORMAL", "ESTUDO"}
        and capable
    )
    result.update(
        {
            "noteri": snapshot,
            "profile_task_capable": capable,
            "operational": operational,
        }
    )
    return result


def recover(
    *,
    confirm: str,
    source_root: Path,
    expected_sha: str,
    evidence_path: Path,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    host: str | None = None,
    platform: str | None = None,
    sha_fn: Callable[[Path], str] = source_sha,
    install_fn=install,
    start_fn=start_supervisor,
    state_fn: Callable[[], dict[str, Any]] = worker_state,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    require_target(host=host, platform=platform)
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise RecoveryError("timeout_invalid")
    expected = str(expected_sha or "").strip().lower()
    if len(expected) != 40 or any(ch not in "0123456789abcdef" for ch in expected):
        raise RecoveryError("expected_sha_invalid")

    source = source_root.resolve()
    if not (source / "orchestrator" / "__init__.py").is_file():
        raise RecoveryError("source_contract_invalid")
    if not (source / "scripts" / "service_supervisor.py").is_file():
        raise RecoveryError("source_contract_invalid")
    observed_sha = sha_fn(source)
    if observed_sha != expected:
        raise RecoveryError("source_sha_mismatch")

    before = state_fn()
    installed = install_fn(
        source_root=source,
        install_root=INSTALL_ROOT,
        mode="worker",
        endpoint=CONTROL_PLANE,
        worker_id=WORKER_ID,
        controller_version=CONTROLLER_VERSION,
        dispatch_priority=20,
        port=8787,
        startup_root=None,
    )
    if str(installed.get("mode") or "") != "worker":
        raise RecoveryError("install_contract_invalid")
    worker_config = Path(str(installed.get("worker_config") or ""))
    startup_path = Path(str(installed.get("startup_path") or ""))
    supervisor_config = Path(str(installed.get("supervisor_config") or ""))
    if not worker_config.is_file() or not startup_path.is_file() or not supervisor_config.is_file():
        raise RecoveryError("installed_runtime_incomplete")

    config = json.loads(worker_config.read_text(encoding="utf-8"))
    if str(config.get("endpoint") or "").rstrip("/") != CONTROL_PLANE:
        raise RecoveryError("worker_endpoint_mismatch")
    if str(config.get("worker_id") or "").casefold() != WORKER_ID:
        raise RecoveryError("worker_identity_mismatch")

    pid = start_fn(INSTALL_ROOT, supervisor_config)
    if not isinstance(pid, int) or pid <= 0:
        raise RecoveryError("supervisor_start_failed")

    deadline = time.monotonic() + timeout_seconds
    after = state_fn()
    while time.monotonic() < deadline and after.get("operational") is not True:
        sleep_fn(2.0)
        after = state_fn()
    if after.get("operational") is not True:
        raise RecoveryError("noteri_worker_not_operational")
    if after.get("profile_task_capable") is not True:
        raise RecoveryError("profile_task_capability_missing")

    payload = {
        "ok": True,
        "environment": "dev",
        "host": EXPECTED_HOST,
        "expected_sha": expected,
        "observed_sha": observed_sha,
        "source_sha_verified": True,
        "control_plane": CONTROL_PLANE,
        "worker_id": WORKER_ID,
        "before": before,
        "after": after,
        "startup_registered": True,
        "supervisor_pid_present": True,
        "task_scheduler_modified": False,
        "production_touched": False,
        "secrets_read": False,
        "rdc_required": False,
    }
    _write_json(evidence_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--evidence-path", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()
    try:
        result = recover(
            confirm=args.confirm,
            source_root=args.source_root,
            expected_sha=args.expected_sha,
            evidence_path=args.evidence_path.resolve(),
            timeout_seconds=args.timeout_seconds,
        )
    except (RecoveryError, OSError, ValueError, json.JSONDecodeError) as exc:
        blocked = {
            "ok": False,
            "environment": "dev",
            "host": EXPECTED_HOST,
            "error_code": str(exc),
            "task_scheduler_modified": False,
            "production_touched": False,
            "secrets_read": False,
            "rdc_required": False,
        }
        _write_json(args.evidence_path.resolve(), blocked)
        print(json.dumps(blocked, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
