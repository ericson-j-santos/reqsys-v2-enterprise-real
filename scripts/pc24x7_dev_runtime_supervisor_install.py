#!/usr/bin/env python3
"""Instala/remove supervisor DEV recorrente no Task Scheduler do usuário.

A tarefa roda no logon e a cada 5 minutos sem exigir privilégio elevado.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

TASK_NAME = "ReqSys-Dev-Runtime-Supervisor"
ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR = ROOT / "scripts" / "pc24x7_dev_runtime_supervisor.py"
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ReqSys" / "PublicRuntime"
WRAPPER = LOG_DIR / "run-dev-supervisor.cmd"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


def write_wrapper() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    python = Path(sys.executable)
    content = (
        "@echo off\r\n"
        f'"{python}" "{SUPERVISOR}" --apply '
        f'>> "{LOG_DIR / "dev-supervisor.log"}" 2>&1\r\n'
    )
    WRAPPER.write_text(content, encoding="utf-8")


def install() -> int:
    write_wrapper()
    command = [
        "schtasks", "/Create", "/F",
        "/TN", TASK_NAME,
        "/TR", str(WRAPPER),
        "/SC", "MINUTE", "/MO", "5",
    ]
    created = run(command)
    if created.returncode != 0:
        print(created.stderr or created.stdout, file=sys.stderr)
        return 2
    # Run once now; failure is surfaced but does not remove the recurring task.
    run(["schtasks", "/Run", "/TN", TASK_NAME])
    print(f"INSTALLED {TASK_NAME} wrapper={WRAPPER}")
    return 0


def uninstall() -> int:
    deleted = run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME])
    if WRAPPER.exists():
        WRAPPER.unlink()
    if deleted.returncode not in (0, 1):
        print(deleted.stderr or deleted.stdout, file=sys.stderr)
        return 2
    print(f"REMOVED {TASK_NAME}")
    return 0


def status() -> int:
    result = run(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"])
    print(result.stdout if result.stdout else result.stderr)
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
