#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time

import psutil


class RecoveryError(RuntimeError):
    pass


def listener_processes() -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = str(proc.info.get("name") or "")
            cmdline = [str(x) for x in (proc.info.get("cmdline") or [])]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        joined = " ".join(cmdline)
        if name.casefold() in {"runner.listener.exe", "runner.worker.exe"} or "Runner.Listener" in joined:
            found.append({"pid": proc.info.get("pid"), "name": name})
    return found


def runner_services() -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if not hasattr(psutil, "win_service_iter"):
        return found
    for service in psutil.win_service_iter():
        try:
            info = service.as_dict()
        except (psutil.Error, OSError):
            continue
        name = str(info.get("name") or "")
        display = str(info.get("display_name") or "")
        haystack = f"{name} {display}".casefold()
        if "actions.runner" in haystack or "github actions runner" in haystack:
            found.append({
                "name": name,
                "display_name": display,
                "status": str(info.get("status") or ""),
            })
    return found


def execute(start: bool) -> dict[str, object]:
    before_processes = listener_processes()
    services = runner_services()
    evidence: dict[str, object] = {
        "host": "DESKTOP-PDQK954",
        "environment": "dev",
        "listener_processes_before": before_processes,
        "services": services,
        "start_requested": start,
        "service_started": False,
        "production_touched": False,
        "secret_value_exposed": False,
    }
    if before_processes:
        evidence["status"] = "ready"
        evidence["listener_processes_after"] = before_processes
        return evidence
    if len(services) != 1:
        evidence["status"] = "blocked"
        evidence["reason"] = "runner_service_ambiguous_or_missing"
        return evidence
    target = services[0]
    service = psutil.win_service_get(str(target["name"]))
    status = service.status()
    if status == "running":
        evidence["status"] = "ready"
        evidence["listener_processes_after"] = listener_processes()
        return evidence
    if not start:
        evidence["status"] = "stopped"
        evidence["reason"] = "runner_service_stopped"
        return evidence

    try:
        service.start()
    except Exception as exc:
        evidence["status"] = "blocked"
        evidence["reason"] = f"service_start_failed:{type(exc).__name__}"
        return evidence

    deadline = time.monotonic() + 45
    last = ""
    while time.monotonic() < deadline:
        try:
            last = service.status()
        except Exception:
            last = "unknown"
        processes = listener_processes()
        if last == "running" and processes:
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
