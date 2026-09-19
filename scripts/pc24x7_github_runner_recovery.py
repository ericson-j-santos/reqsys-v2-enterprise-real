#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import os
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


def runner_services() -> list[dict[str, str]]:
    result = _run([_tool("sc.exe"), "query", "type=", "service", "state=", "all"], timeout=60)
    if result.returncode != 0:
        return []
    blocks = re.split(r"(?=SERVICE_NAME:)", result.stdout or "")
    found: list[dict[str, str]] = []
    for block in blocks:
        match = re.search(r"SERVICE_NAME:\s*(\S+)", block, flags=re.IGNORECASE)
        if not match:
            continue
        name = match.group(1)
        if "actions.runner" not in name.casefold():
            continue
        state_match = re.search(r"STATE\s*:\s*\d+\s+(\S+)", block, flags=re.IGNORECASE)
        found.append({"name": name, "status": state_match.group(1).upper() if state_match else "UNKNOWN"})
    return found


def runner_tasks() -> list[dict[str, str]]:
    tool = shutil.which("schtasks.exe")
    if not tool:
        return []
    result = _run([tool, "/Query", "/FO", "CSV", "/V", "/NH"], timeout=90)
    if result.returncode != 0:
        return []
    found: list[dict[str, str]] = []
    for row in csv.reader(io.StringIO(result.stdout or "")):
        if not row:
            continue
        joined = " ".join(row).casefold()
        if not any(marker in joined for marker in ("runner.listener", "actions-runner", "github actions runner", "githubactionsrunner")):
            continue
        task_name = row[1].strip() if len(row) > 1 else row[0].strip()
        found.append({"task_name": task_name})
    unique = {item["task_name"]: item for item in found if item["task_name"]}
    return list(unique.values())


def runner_roots() -> list[dict[str, str]]:
    roots: list[Path] = []
    explicit = [
        Path(r"C:\actions-runner"),
        Path(r"C:\github-actions-runner"),
        Path(r"C:\dev\actions-runner"),
        Path(r"C:\dev\github-actions-runner"),
        Path(r"C:\ProgramData\GitHubActionsRunner"),
        Path(r"C:\Users\Windows\actions-runner"),
        Path(r"C:\Users\Windows\github-actions-runner"),
    ]
    roots.extend(explicit)
    for parent in (Path(r"C:\dev"), Path(r"C:\Users\Windows")):
        try:
            for child in parent.iterdir():
                if child.is_dir():
                    roots.append(child)
        except OSError:
            pass
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = str(root.resolve())
        except OSError:
            continue
        key = resolved.casefold()
        if key in seen:
            continue
        seen.add(key)
        listener = root / "bin" / "Runner.Listener.exe"
        config = root / ".runner"
        if listener.is_file() and config.is_file():
            found.append({"root": resolved, "listener": str(listener)})
    return found


def _start_task(task_name: str) -> bool:
    tool = _tool("schtasks.exe")
    result = _run([tool, "/Run", "/TN", task_name], timeout=30)
    return result.returncode == 0


def _start_listener(listener: Path, root: Path) -> bool:
    flags = 0
    for name in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP", "CREATE_NO_WINDOW"):
        flags |= int(getattr(subprocess, name, 0))
    try:
        subprocess.Popen(
            [str(listener), "run"],
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            creationflags=flags,
            close_fds=True,
        )
        return True
    except OSError:
        return False


def execute(start: bool) -> dict[str, object]:
    before = listener_processes()
    services = runner_services()
    tasks = runner_tasks()
    roots = runner_roots()
    evidence: dict[str, object] = {
        "host": "DESKTOP-PDQK954",
        "environment": "dev",
        "listener_processes_before": before,
        "services": services,
        "tasks": tasks,
        "runner_roots": roots,
        "start_requested": start,
        "runner_started": False,
        "production_touched": False,
        "secret_value_exposed": False,
    }
    if before:
        evidence["status"] = "ready"
        evidence["listener_processes_after"] = before
        return evidence
    if not start:
        evidence["status"] = "stopped"
        return evidence

    attempted = False
    if len(tasks) == 1:
        attempted = _start_task(tasks[0]["task_name"])
        evidence["start_method"] = "scheduled_task"
    elif len(services) == 1:
        result = _run([_tool("sc.exe"), "start", services[0]["name"]], timeout=30)
        attempted = result.returncode in {0, 1056}
        evidence["start_method"] = "windows_service"
    elif len(roots) == 1:
        root = Path(roots[0]["root"])
        listener = Path(roots[0]["listener"])
        attempted = _start_listener(listener, root)
        evidence["start_method"] = "runner_listener_direct"
    else:
        evidence["status"] = "blocked"
        evidence["reason"] = "runner_target_ambiguous_or_missing"
        return evidence

    if not attempted:
        evidence["status"] = "blocked"
        evidence["reason"] = "runner_start_failed"
        return evidence

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        processes = listener_processes()
        if processes:
            evidence["status"] = "ready"
            evidence["runner_started"] = True
            evidence["listener_processes_after"] = processes
            return evidence
        time.sleep(2)

    evidence["status"] = "blocked"
    evidence["reason"] = "runner_start_timeout"
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
