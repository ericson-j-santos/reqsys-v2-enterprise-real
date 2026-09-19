#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import subprocess
import time
from pathlib import Path


class RecoveryError(RuntimeError):
    pass


def _tool(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RecoveryError(f"tool_missing:{name}")
    return resolved


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )


def listener_processes() -> list[dict[str, object]]:
    result = _run([_tool("tasklist.exe"), "/FO", "CSV", "/NH"])
    if result.returncode != 0:
        return []
    found: list[dict[str, object]] = []
    for row in csv.reader(io.StringIO(result.stdout or "")):
        if len(row) < 2:
            continue
        name = row[0].strip()
        if name.casefold() not in {"runner.listener.exe", "runner.worker.exe"}:
            continue
        try:
            pid = int(row[1])
        except ValueError:
            pid = 0
        found.append({"pid": pid, "name": name})
    return found


def _query_all_services() -> str:
    result = _run([_tool("sc.exe"), "query", "type=", "service", "state=", "all"], timeout=60)
    if result.returncode != 0:
        raise RecoveryError("service_inventory_failed")
    return result.stdout or ""


def runner_services() -> list[dict[str, str]]:
    text = _query_all_services()
    blocks = re.split(r"(?=SERVICE_NAME:)", text)
    found: list[dict[str, str]] = []
    for block in blocks:
        match = re.search(r"SERVICE_NAME:\s*(\S+)", block, flags=re.IGNORECASE)
        if not match:
            continue
        name = match.group(1)
        if "actions.runner" not in name.casefold():
            continue
        state_match = re.search(r"STATE\s*:\s*\d+\s+(\S+)", block, flags=re.IGNORECASE)
        state = state_match.group(1).upper() if state_match else "UNKNOWN"
        found.append({"name": name, "status": state})
    return found


def service_status(service_name: str) -> str:
    result = _run([_tool("sc.exe"), "query", service_name], timeout=30)
    if result.returncode != 0:
        return "UNKNOWN"
    match = re.search(r"STATE\s*:\s*\d+\s+(\S+)", result.stdout or "", flags=re.IGNORECASE)
    return match.group(1).upper() if match else "UNKNOWN"


def execute(start: bool) -> dict[str, object]:
    before = listener_processes()
    services = runner_services()
    evidence: dict[str, object] = {
        "host": "DESKTOP-PDQK954",
        "environment": "dev",
        "listener_processes_before": before,
        "services": services,
        "start_requested": start,
        "service_started": False,
        "production_touched": False,
        "secret_value_exposed": False,
    }
    if before:
        evidence["status"] = "ready"
        evidence["listener_processes_after"] = before
        return evidence
    if len(services) != 1:
        evidence["status"] = "blocked"
        evidence["reason"] = "runner_service_ambiguous_or_missing"
        return evidence

    service_name = services[0]["name"]
    current = service_status(service_name)
    if current == "RUNNING":
        evidence["status"] = "ready"
        evidence["listener_processes_after"] = listener_processes()
        return evidence
    if not start:
        evidence["status"] = "stopped"
        evidence["reason"] = f"runner_service_{current.lower()}"
        return evidence

    started = _run([_tool("sc.exe"), "start", service_name], timeout=30)
    if started.returncode not in {0, 1056}:
        evidence["status"] = "blocked"
        evidence["reason"] = f"service_start_failed:exit_{started.returncode}"
        return evidence

    deadline = time.monotonic() + 60
    last = current
    while time.monotonic() < deadline:
        last = service_status(service_name)
        processes = listener_processes()
        if last == "RUNNING" and processes:
            evidence["status"] = "ready"
            evidence["service_started"] = True
            evidence["listener_processes_after"] = processes
            return evidence
        time.sleep(2)

    evidence["status"] = "blocked"
    evidence["reason"] = f"runner_start_timeout:{last}"
    evidence["listener_processes_after"] = listener_processes()
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()
    try:
        evidence = execute(args.start)
    except Exception as exc:
        evidence = {
            "status": "blocked",
            "reason": f"unexpected:{type(exc).__name__}",
            "environment": "dev",
            "production_touched": False,
            "secret_value_exposed": False,
        }
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0 if evidence.get("status") == "ready" else 4


if __name__ == "__main__":
    raise SystemExit(main())
