from __future__ import annotations

import argparse
import importlib.util
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

EXPECTED_HOST = "Noteri"
INSTALL_ROOT = Path(r"C:\dev\chatgpt-workers\reqsys-orchestrator-24x7-runtime")
CONTROL_PLANE = "http://DESKTOP-PDQK954:8787"
WORKER_ID = "noteri"
PROFILE_TASK = "host.profile.set.v1"
CONFIRM = "RECOVER-NOTERI-INSTALLED-ORCHESTRATOR-WORKER-DEV"
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


def workflow_sha(source_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    value = completed.stdout.strip().lower()
    if completed.returncode != 0 or len(value) != 40 or any(
        ch not in "0123456789abcdef" for ch in value
    ):
        raise RecoveryError("workflow_sha_unavailable")
    return value


def inspect_installed_contract(install_root: Path = INSTALL_ROOT) -> dict[str, Any]:
    root = install_root.resolve()
    maintenance = root / "orchestrator" / "maintenance.py"
    worker_agent = root / "orchestrator" / "worker_agent.py"
    helper = root / "scripts" / "install_windows_autostart.py"
    service_config = root / "service-config.json"
    worker_config = root / "worker-config.json"
    required = [maintenance, worker_agent, helper, service_config, worker_config]
    if not all(path.is_file() for path in required):
        raise RecoveryError("installed_runtime_incomplete")

    maintenance_text = maintenance.read_text(encoding="utf-8")
    worker_text = worker_agent.read_text(encoding="utf-8")
    capability_code_present = (
        'PROFILE_SET_TASK = "host.profile.set.v1"' in maintenance_text
        and "PROFILE_SET_TASK" in worker_text
        and "safe_task_types" in worker_text
    )
    if not capability_code_present:
        raise RecoveryError("installed_profile_capability_code_missing")

    try:
        service = json.loads(service_config.read_text(encoding="utf-8"))
        worker = json.loads(worker_config.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecoveryError("installed_config_invalid") from exc
    if not isinstance(service, dict) or not isinstance(worker, dict):
        raise RecoveryError("installed_config_invalid")
    if str(service.get("mode") or "") != "worker":
        raise RecoveryError("installed_service_mode_invalid")
    if str(worker.get("worker_id") or "").casefold() != WORKER_ID:
        raise RecoveryError("installed_worker_identity_invalid")
    if str(worker.get("endpoint") or "").rstrip("/") != CONTROL_PLANE:
        raise RecoveryError("installed_worker_endpoint_invalid")

    runtime_version = None
    version_path = root / "runtime-version.json"
    if version_path.is_file():
        try:
            raw_version = json.loads(version_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw_version = None
        if isinstance(raw_version, dict):
            candidate = str(
                raw_version.get("source_sha")
                or raw_version.get("sha")
                or raw_version.get("expected_sha")
                or ""
            ).strip().lower()
            if len(candidate) == 40 and all(ch in "0123456789abcdef" for ch in candidate):
                runtime_version = candidate

    return {
        "install_root": str(root),
        "service_mode": "worker",
        "worker_id": WORKER_ID,
        "endpoint": CONTROL_PLANE,
        "profile_capability_code_present": True,
        "runtime_source_sha": runtime_version,
        "helper_path": str(helper),
        "service_config_path": str(service_config),
    }


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
    result: dict[str, Any] = {
        "reachable": status is not None,
        "http_status": status,
        "payload_valid": status == 200 and isinstance(workers, list),
        "match_count": None,
        "operational": False,
        "profile_task_capable": False,
    }
    if status != 200 or not isinstance(workers, list):
        return result

    matches = [
        item
        for item in workers
        if isinstance(item, dict)
        and str(item.get("worker_id") or "").casefold() == WORKER_ID
        and str(item.get("device_name") or "").casefold() == EXPECTED_HOST.casefold()
    ]
    result["match_count"] = len(matches)
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
    capable = isinstance(safe_task_types, list) and PROFILE_TASK in safe_task_types
    sanitized = {
        "fresh": worker.get("fresh") is True,
        "controller_online": worker.get("controller_online") is True,
        "auth_valid": worker.get("auth_valid") is True,
        "profile": profile,
    }
    operational = (
        sanitized["fresh"]
        and sanitized["controller_online"]
        and sanitized["auth_valid"]
        and profile in {"NORMAL", "ESTUDO"}
        and capable
    )
    result.update(
        {
            "noteri": sanitized,
            "profile_task_capable": capable,
            "operational": operational,
        }
    )
    return result


def start_installed_supervisor(
    contract: dict[str, Any],
    install_root: Path = INSTALL_ROOT,
) -> int:
    helper_path = Path(str(contract["helper_path"]))
    spec = importlib.util.spec_from_file_location(
        "_reqsys_installed_orchestrator_autostart",
        helper_path,
    )
    if spec is None or spec.loader is None:
        raise RecoveryError("installed_helper_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    starter = getattr(module, "start_supervisor", None)
    if not callable(starter):
        raise RecoveryError("installed_start_supervisor_missing")

    previous = os.environ.pop("RUNNER_TRACKING_ID", None)
    try:
        pid = starter(
            install_root,
            Path(str(contract["service_config_path"])),
        )
    finally:
        if previous is not None:
            os.environ["RUNNER_TRACKING_ID"] = previous
    if not isinstance(pid, int) or pid <= 0:
        raise RecoveryError("supervisor_start_failed")
    return pid


def recover(
    *,
    confirm: str,
    source_root: Path,
    expected_workflow_sha: str,
    evidence_path: Path,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    host: str | None = None,
    platform: str | None = None,
    sha_fn: Callable[[Path], str] = workflow_sha,
    contract_fn: Callable[[], dict[str, Any]] = inspect_installed_contract,
    start_fn: Callable[[dict[str, Any]], int] = start_installed_supervisor,
    state_fn: Callable[[], dict[str, Any]] = worker_state,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    require_target(host=host, platform=platform)
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise RecoveryError("timeout_invalid")
    expected = str(expected_workflow_sha or "").strip().lower()
    if len(expected) != 40 or any(ch not in "0123456789abcdef" for ch in expected):
        raise RecoveryError("expected_workflow_sha_invalid")

    source = source_root.resolve()
    observed = sha_fn(source)
    if observed != expected:
        raise RecoveryError("workflow_sha_mismatch")

    contract = contract_fn()
    before = state_fn()
    pid = start_fn(contract)
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
        "workflow_expected_sha": expected,
        "workflow_observed_sha": observed,
        "workflow_sha_verified": True,
        "installed_contract": {
            "service_mode": contract["service_mode"],
            "worker_id": contract["worker_id"],
            "endpoint": contract["endpoint"],
            "profile_capability_code_present": contract[
                "profile_capability_code_present"
            ],
            "runtime_source_sha": contract.get("runtime_source_sha"),
        },
        "before": before,
        "after": after,
        "supervisor_pid_present": True,
        "runner_tracking_removed_before_start": True,
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
    parser.add_argument("--expected-workflow-sha", required=True)
    parser.add_argument("--evidence-path", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()
    try:
        result = recover(
            confirm=args.confirm,
            source_root=args.source_root,
            expected_workflow_sha=args.expected_workflow_sha,
            evidence_path=args.evidence_path.resolve(),
            timeout_seconds=args.timeout_seconds,
        )
    except (RecoveryError, OSError, ValueError, KeyError) as exc:
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
