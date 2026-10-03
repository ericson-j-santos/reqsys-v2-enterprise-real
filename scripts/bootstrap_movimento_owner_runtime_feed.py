#!/usr/bin/env python3
"""Instala o feed owner-managed como worker persistente no Noteri."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTOR_SOURCE = ROOT / "scripts" / "movimento_owner_runtime_projector.py"
WORKER_SOURCE = ROOT / "scripts" / "movimento_owner_runtime_feed_worker.py"

LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
RUNTIME = LOCALAPPDATA / "ReqSys" / "OwnerRuntimeFeed"
PROJECTOR_RUNTIME = RUNTIME / "projector.py"
WORKER_RUNTIME = RUNTIME / "worker.py"
CONFIG = RUNTIME / "config.json"
PID_FILE = RUNTIME / "worker.pid"
LOG_FILE = RUNTIME / "worker.log"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "ReqSysOwnerRuntimeFeed"


def _pythonw() -> str:
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return str(candidate if candidate.is_file() else Path(sys.executable))


def _process_alive(pid: int) -> bool:
    if os.name != "nt" or pid <= 0:
        return False
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def _current_pid() -> int | None:
    if not PID_FILE.is_file():
        return None
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None
    return pid if _process_alive(pid) else None


def _command() -> list[str]:
    return [
        _pythonw(),
        str(WORKER_RUNTIME),
        "--config",
        str(CONFIG),
        "--projector",
        str(PROJECTOR_RUNTIME),
    ]


def _register_autostart(command: list[str]) -> bool:
    if os.name != "nt":
        return False
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command))
    return True


def _autostart_registered() -> bool:
    if os.name != "nt":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, RUN_NAME)
        return bool(str(value).strip())
    except OSError:
        return False


def install(runtime_base: str, interval_seconds: int) -> dict:
    if interval_seconds < 300:
        raise RuntimeError("interval_too_short")

    owner_root = LOCALAPPDATA / "ReqSys" / "OwnerGateway"
    owner_config = owner_root / "config.json"
    owner_token = owner_root / "service.token"
    if not owner_config.is_file() or not owner_token.is_file():
        raise RuntimeError("owner_gateway_not_ready")

    RUNTIME.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROJECTOR_SOURCE, PROJECTOR_RUNTIME)
    shutil.copy2(WORKER_SOURCE, WORKER_RUNTIME)

    config = {
        "schema_version": "1.0.0",
        "runtime_base": runtime_base.rstrip("/"),
        "interval_seconds": interval_seconds,
        "owner_config": str(owner_config),
        "owner_token_file": str(owner_token),
    }
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    command = _command()
    autostart = _register_autostart(command)
    pid = _current_pid()
    started = False
    if pid is None:
        log = LOG_FILE.open("a", encoding="utf-8")
        creationflags = 0
        if os.name == "nt":
            creationflags = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
        process = subprocess.Popen(
            command,
            cwd=RUNTIME,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=creationflags,
        )
        pid = int(process.pid)
        PID_FILE.write_text(str(pid), encoding="utf-8")
        started = True

    return {
        "status": "passed" if autostart and pid and _process_alive(pid) else "blocked",
        "runtime_base": runtime_base.rstrip("/"),
        "interval_seconds": interval_seconds,
        "autostart_registered": autostart,
        "worker_running": bool(pid and _process_alive(pid)),
        "worker_started": started,
        "owner_gateway_ready": True,
        "secret_exposed": False,
        "production_touched": False,
    }


def status() -> dict:
    pid = _current_pid()
    return {
        "status": "passed"
        if CONFIG.is_file() and PROJECTOR_RUNTIME.is_file() and WORKER_RUNTIME.is_file()
        and _autostart_registered() and pid
        else "blocked",
        "configured": CONFIG.is_file(),
        "autostart_registered": _autostart_registered(),
        "worker_running": bool(pid),
        "secret_exposed": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("install", "status"))
    parser.add_argument("--runtime-base", default="http://DESKTOP-PDQK954:8081")
    parser.add_argument("--interval-seconds", type=int, default=900)
    args = parser.parse_args()

    result = (
        install(args.runtime_base, args.interval_seconds)
        if args.command == "install"
        else status()
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
