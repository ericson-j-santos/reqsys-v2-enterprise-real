#!/usr/bin/env python3
"""Instala/remove o supervisor DEV recorrente e persistente do PC24x7."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TASK_NAME = "ReqSys-Dev-Runtime-Supervisor"
SUPERVISOR_INTERVAL_MINUTES = 6
LOCATOR_TTL_MINUTES = 15
MISSED_CYCLE_TOLERANCE = 1
NTFY_ANONYMOUS_DAILY_MESSAGE_LIMIT = 250
MAX_SCHEDULED_PUBLICATIONS_PER_DAY = (
    (24 * 60) + SUPERVISOR_INTERVAL_MINUTES - 1
) // SUPERVISOR_INTERVAL_MINUTES
ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCRIPTS = (
    "pc24x7_dev_runtime_supervisor.py",
    "self_hosted_dev_maintenance.py",
    "self_hosted_dev_candidate_control.py",
    "reqsys_self_hosted_dev_publish.py",
    "pc24x7_public_dev_tunnel.py",
    "pc24x7_dev_locator_publisher.py",
)
BASE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ReqSys"
RUNTIME_DIR = BASE_DIR / "RuntimeSupervisor"
SCRIPTS_DIR = RUNTIME_DIR / "scripts"
LOG_DIR = BASE_DIR / "PublicRuntime"
RUNTIME_PYTHON_DIR = RUNTIME_DIR / "python"
RUNTIME_PYTHON = RUNTIME_PYTHON_DIR / "Scripts" / "python.exe"
RUNTIME_PYTHON_PACKAGES = ("cryptography==50.0.0", "pywin32==312")
PERSISTENT_SUPERVISOR = SCRIPTS_DIR / "pc24x7_dev_runtime_supervisor.py"
WRAPPER = LOG_DIR / "run-dev-supervisor.cmd"
MANIFEST = RUNTIME_DIR / "manifest.json"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def source_head() -> str | None:
    completed = run(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
    return completed.stdout.strip() if completed.returncode == 0 else None


def materialize_runtime() -> dict[str, str]:
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for name in SOURCE_SCRIPTS:
        source = ROOT / "scripts" / name
        target = SCRIPTS_DIR / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, target)
        copied[name] = str(target)

    payload = {
        "schema_version": "2.0.0",
        "source_head": source_head(),
        "source_root": str(ROOT),
        "supervisor": str(PERSISTENT_SUPERVISOR),
        "runtime_python": str(RUNTIME_PYTHON),
        "runtime_python_packages": list(RUNTIME_PYTHON_PACKAGES),
        "cost_policy": "zero_additional_cost",
        "supervisor_interval_minutes": SUPERVISOR_INTERVAL_MINUTES,
        "locator_ttl_minutes": LOCATOR_TTL_MINUTES,
        "missed_cycle_tolerance": MISSED_CYCLE_TOLERANCE,
        "max_scheduled_publications_per_day": MAX_SCHEDULED_PUBLICATIONS_PER_DAY,
        "ntfy_anonymous_daily_message_limit": NTFY_ANONYMOUS_DAILY_MESSAGE_LIMIT,
    }
    MANIFEST.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return copied


def runtime_python_ready(python: Path) -> bool:
    if not python.is_file():
        return False
    completed = run([
        str(python),
        "-c",
        "import cryptography, win32crypt; print('runtime_python_ready')",
    ])
    return completed.returncode == 0 and completed.stdout.strip() == "runtime_python_ready"


def ensure_runtime_python() -> Path:
    if os.name != "nt":
        raise RuntimeError("windows_runtime_python_required")
    if runtime_python_ready(RUNTIME_PYTHON):
        return RUNTIME_PYTHON
    if not RUNTIME_PYTHON.is_file():
        created = run([sys.executable, "-m", "venv", str(RUNTIME_PYTHON_DIR)])
        if created.returncode != 0 or not RUNTIME_PYTHON.is_file():
            raise RuntimeError("runtime_python_venv_failed")
    installed = run([
        str(RUNTIME_PYTHON),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        *RUNTIME_PYTHON_PACKAGES,
    ])
    if installed.returncode != 0 or not runtime_python_ready(RUNTIME_PYTHON):
        raise RuntimeError("runtime_python_dependencies_failed")
    return RUNTIME_PYTHON


def write_wrapper(python: Path) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    WRAPPER.write_text(
        "@echo off\r\n"
        f'cd /d "{RUNTIME_DIR}"\r\n'
        f'"{python}" -m scripts.pc24x7_dev_runtime_supervisor --apply '
        f'>> "{LOG_DIR / "dev-supervisor.log"}" 2>&1\r\n',
        encoding="utf-8",
    )


def harden_task_settings(python: Path) -> dict:
    if os.name != "nt":
        return {"skipped": "non_windows"}
    helper = r'''import json
import os
import sys

import win32com.client

task_name = sys.argv[1]
service = win32com.client.Dispatch("Schedule.Service")
service.Connect()
folder = service.GetFolder("\\")
task = folder.GetTask(task_name)
definition = task.Definition
settings = definition.Settings
settings.DisallowStartIfOnBatteries = False
settings.StopIfGoingOnBatteries = False
settings.StartWhenAvailable = True
settings.ExecutionTimeLimit = "PT10M"

TASK_CREATE_OR_UPDATE = 6
TASK_LOGON_INTERACTIVE_TOKEN = 3
folder.RegisterTaskDefinition(
    task_name,
    definition,
    TASK_CREATE_OR_UPDATE,
    definition.Principal.UserId or os.environ.get("USERNAME"),
    None,
    TASK_LOGON_INTERACTIVE_TOKEN,
)
registered = folder.GetTask(task_name)
current = registered.Definition.Settings
print(json.dumps({
    "DisallowStartIfOnBatteries": bool(current.DisallowStartIfOnBatteries),
    "StopIfGoingOnBatteries": bool(current.StopIfGoingOnBatteries),
    "StartWhenAvailable": bool(current.StartWhenAvailable),
    "ExecutionTimeLimit": str(current.ExecutionTimeLimit),
}, sort_keys=True))
'''
    completed = run([str(python), "-c", helper, TASK_NAME])
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"task_settings_hardening_failed: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("task_settings_hardening_invalid_output") from exc


def install() -> int:
    copied = materialize_runtime()
    try:
        runtime_python = ensure_runtime_python()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_wrapper(runtime_python)
    created = run([
        "schtasks", "/Create", "/F",
        "/TN", TASK_NAME,
        "/TR", str(WRAPPER),
        "/SC", "MINUTE", "/MO", str(SUPERVISOR_INTERVAL_MINUTES),
    ])
    if created.returncode != 0:
        print(created.stderr or created.stdout, file=sys.stderr)
        return 2

    try:
        settings = harden_task_settings(runtime_python)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    triggered = run(["schtasks", "/Run", "/TN", TASK_NAME])
    print(json.dumps({
        "status": "installed",
        "task": TASK_NAME,
        "wrapper": str(WRAPPER),
        "persistent_supervisor": str(PERSISTENT_SUPERVISOR),
        "runtime_python": str(runtime_python),
        "runtime_python_ready": True,
        "copied": copied,
        "settings": settings,
        "trigger_returncode": triggered.returncode,
    }, ensure_ascii=True, sort_keys=True))
    return 0


def uninstall() -> int:
    deleted = run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME])
    if WRAPPER.exists():
        WRAPPER.unlink()
    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)
    if deleted.returncode not in (0, 1):
        print(deleted.stderr or deleted.stdout, file=sys.stderr)
        return 2
    print(f"REMOVED {TASK_NAME}")
    return 0


def status() -> int:
    result = run(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"])
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else None
    print(json.dumps({
        "task_query_returncode": result.returncode,
        "task": result.stdout if result.stdout else result.stderr,
        "manifest": manifest,
        "wrapper_exists": WRAPPER.is_file(),
        "persistent_supervisor_exists": PERSISTENT_SUPERVISOR.is_file(),
    }, ensure_ascii=True, sort_keys=True))
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("install")
    sub.add_parser("uninstall")
    sub.add_parser("status")
    args = parser.parse_args()
    return {"install": install, "uninstall": uninstall, "status": status}[args.action]()


if __name__ == "__main__":
    raise SystemExit(main())
