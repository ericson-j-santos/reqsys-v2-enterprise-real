#!/usr/bin/env python3
"""Launcher UAC governado para provisionar o agente NORMAL/ESTUDO antes do login."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import noteri_host_profile_agent_persistence as persistence

LAUNCH_CONFIRM = "LAUNCH-NOTERI-HEADLESS-UAC"
SW_SHOWNORMAL = 1


def validate_launcher(*, host: str, platform: str, confirm: str) -> None:
    if host.casefold() != "noteri":
        raise RuntimeError("launcher permitido somente no host Noteri")
    if platform != "nt":
        raise RuntimeError("launcher UAC exige Windows")
    if confirm != LAUNCH_CONFIRM:
        raise RuntimeError("confirmação UAC inválida")


def build_elevated_arguments(repo_root: Path) -> str:
    persistence_script = Path(__file__).resolve().with_name("noteri_host_profile_agent_persistence.py")
    argv = [
        str(persistence_script),
        "install-headless",
        "--repo-root",
        str(repo_root.resolve()),
        "--confirm",
        persistence.HEADLESS_CONFIRM,
    ]
    return subprocess.list2cmdline(argv)


def headless_ready() -> bool:
    task = persistence.task_status()
    return (
        task.get("exists") is True
        and task.get("principal_logon_type") == persistence.TASK_LOGON_S4U
        and task.get("principal_run_level") == persistence.TASK_RUNLEVEL_LUA
        and any(item.get("type") == persistence.TASK_TRIGGER_BOOT for item in task.get("triggers", []))
    )


def launch(repo_root: Path, *, confirm: str, timeout_seconds: int) -> dict:
    validate_launcher(
        host=socket.gethostname(),
        platform=os.name,
        confirm=confirm,
    )

    if persistence.is_admin():
        result = persistence.install_headless(repo_root.resolve(), confirm=persistence.HEADLESS_CONFIRM)
        return {"ok": bool(result.get("ok")), "mode": "already_elevated", "result": result}

    params = build_elevated_arguments(repo_root)
    rc = int(
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            str(repo_root.resolve()),
            SW_SHOWNORMAL,
        )
    )
    if rc <= 32:
        raise RuntimeError(f"uac_launch_failed:{rc}")

    deadline = time.monotonic() + max(5, min(timeout_seconds, 120))
    while time.monotonic() < deadline:
        if headless_ready():
            metadata = {}
            path = persistence.metadata_path()
            if path.is_file():
                metadata = json.loads(path.read_text(encoding="utf-8"))
            return {
                "ok": True,
                "mode": "uac",
                "result": "NOTERI_HEADLESS_UAC_PROVISIONED",
                "task": persistence.task_status(),
                "metadata": metadata,
                "agent_healthy": persistence.probe_agent() is not None,
            }
        time.sleep(1.0)

    return {
        "ok": False,
        "mode": "uac",
        "result": "UAC_APPROVAL_OR_PROVISIONING_PENDING",
        "task": persistence.task_status(),
        "agent_healthy": persistence.probe_agent() is not None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Provisiona headless NORMAL/ESTUDO via UAC")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()
    try:
        result = launch(
            args.repo_root,
            confirm=args.confirm,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
