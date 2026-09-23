#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
TASK_NAME = r"\Automation\ReqSysOrchestrator24x7"
BASE_URL = "http://127.0.0.1:8787"
EXPECTED_ACTION_MARKERS = ("-m", "scripts.service_supervisor", "--config")


class RecoveryError(RuntimeError):
    pass


def schtasks_path() -> Path:
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return Path(root) / "System32" / "schtasks.exe"


def request_json(path: str, timeout: float = 3.0) -> tuple[int | None, dict[str, Any] | None]:
    request = urllib.request.Request(
        BASE_URL + path,
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            return int(response.status), payload if isinstance(payload, dict) else None
    except urllib.error.HTTPError as exc:
        return int(exc.code), None
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None, None


def task_snapshot() -> dict[str, Any]:
    exe = schtasks_path()
    completed = subprocess.run(
        [str(exe), "/Query", "/TN", TASK_NAME, "/XML"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        return {"exists": False, "action_valid": False, "enabled": None}
    try:
        root = ET.fromstring(completed.stdout.lstrip("\ufeff"))
    except ET.ParseError as exc:
        raise RecoveryError("task_xml_invalid") from exc

    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    enabled_node = root.find("./t:Settings/t:Enabled", ns)
    command_node = root.find("./t:Actions/t:Exec/t:Command", ns)
    args_node = root.find("./t:Actions/t:Exec/t:Arguments", ns)
    arguments = (args_node.text or "") if args_node is not None else ""
    command = (command_node.text or "") if command_node is not None else ""
    action_valid = bool(command.strip()) and all(marker in arguments for marker in EXPECTED_ACTION_MARKERS)
    enabled = True if enabled_node is None else (enabled_node.text or "").strip().casefold() == "true"
    return {"exists": True, "action_valid": action_valid, "enabled": enabled}


def run_task() -> None:
    completed = subprocess.run(
        [str(schtasks_path()), "/Run", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        raise RecoveryError("scheduled_task_run_failed")


def ready_snapshot() -> dict[str, Any]:
    health_status, _ = request_json("/healthz")
    ready_status, _ = request_json("/readyz")
    return {
        "healthz_status": health_status,
        "readyz_status": ready_status,
        "ready": health_status == 200 and ready_status == 200,
    }


def wait_ready(timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = ready_snapshot()
    while not last["ready"] and time.monotonic() < deadline:
        time.sleep(2)
        last = ready_snapshot()
    return last


def sanitized_registry() -> dict[str, Any]:
    status, payload = request_json("/v1/workers")
    result: dict[str, Any] = {
        "reachable": status == 200,
        "http_status": status,
        "payload_valid": False,
        "noteri_match_count": None,
    }
    if status != 200 or not isinstance(payload, dict):
        return result
    workers = payload.get("workers")
    if not isinstance(workers, list):
        return result
    matches = [
        worker for worker in workers
        if isinstance(worker, dict)
        and str(worker.get("device_name") or "").strip().casefold() == "noteri"
    ]
    result["payload_valid"] = True
    result["noteri_match_count"] = len(matches)
    if len(matches) == 1:
        worker = matches[0]
        profile = str(worker.get("profile") or "").strip().upper()
        result["noteri"] = {
            "fresh": worker.get("fresh") is True,
            "controller_online": worker.get("controller_online") is True,
            "auth_valid": worker.get("auth_valid") is True,
            "eligible": worker.get("eligible") is True,
            "profile": profile if profile in {"NORMAL", "ESTUDO"} else "UNKNOWN",
        }
    return result


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def execute(evidence_path: Path, timeout_seconds: int) -> int:
    evidence: dict[str, Any] = {
        "ok": False,
        "host": socket.gethostname(),
        "environment": "dev",
        "production_touched": False,
        "secrets_read": False,
        "rdc_required": False,
        "task_name": TASK_NAME,
    }
    try:
        if os.name != "nt" or socket.gethostname().casefold() != EXPECTED_HOST.casefold():
            raise RecoveryError("unexpected_host")

        task = task_snapshot()
        evidence["task"] = task
        if not task["exists"]:
            raise RecoveryError("scheduled_task_missing")
        if task["enabled"] is not True:
            raise RecoveryError("scheduled_task_disabled")
        if task["action_valid"] is not True:
            raise RecoveryError("scheduled_task_action_invalid")

        before = ready_snapshot()
        evidence["before"] = before
        evidence["task_run_requested"] = False
        if not before["ready"]:
            run_task()
            evidence["task_run_requested"] = True

        after = wait_ready(timeout_seconds)
        evidence["after"] = after
        if not after["ready"]:
            raise RecoveryError("control_plane_not_ready_after_recovery")

        registry = sanitized_registry()
        evidence["registry"] = registry
        if not registry.get("reachable") or not registry.get("payload_valid"):
            raise RecoveryError("worker_registry_unavailable")
        if registry.get("noteri_match_count") != 1:
            raise RecoveryError("noteri_worker_cardinality_invalid")
        noteri = registry.get("noteri") or {}
        if not all(noteri.get(key) is True for key in ("fresh", "controller_online", "auth_valid", "eligible")):
            raise RecoveryError("noteri_worker_not_operational")

        evidence["ok"] = True
        evidence["result"] = "ENGINEERING_ORCHESTRATOR_RECOVERED"
        atomic_write(evidence_path, evidence)
        print(json.dumps(evidence, sort_keys=True))
        return 0
    except RecoveryError as exc:
        evidence["error"] = str(exc)
        evidence["registry"] = evidence.get("registry") or sanitized_registry()
        atomic_write(evidence_path, evidence)
        print(json.dumps(evidence, sort_keys=True))
        return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-path", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()
    if not 10 <= args.timeout_seconds <= 120:
        raise SystemExit("timeout_seconds_out_of_range")
    return execute(args.evidence_path, args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
