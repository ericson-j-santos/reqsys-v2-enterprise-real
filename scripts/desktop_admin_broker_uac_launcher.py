#!/usr/bin/env python3
"""Launcher UAC governado para ativar o Desktop Admin Broker."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import desktop_admin_broker as broker

LAUNCH_CONFIRM = "LAUNCH-DESKTOP-ADMIN-BROKER-UAC"
SW_SHOWNORMAL = 1


def validate_launcher(*, host: str, platform: str, confirm: str) -> None:
    if host.casefold() != broker.EXPECTED_HOST.casefold():
        raise RuntimeError(f"launcher permitido somente no host {broker.EXPECTED_HOST}")
    if platform != "nt":
        raise RuntimeError("launcher UAC exige Windows")
    if confirm != LAUNCH_CONFIRM:
        raise RuntimeError("confirmação UAC inválida")


def is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def default_metadata_path() -> Path:
    return broker.default_runtime_root() / "metadata.json"


def task_ready(task: dict[str, Any]) -> bool:
    return (
        task.get("exists") is True
        and task.get("trigger_at_startup") is True
        and str(task.get("logon_type") or "").casefold() == "s4u"
        and str(task.get("run_level") or "").casefold() == "highest"
    )


def load_installation(metadata_path: Path) -> dict[str, Any]:
    return broker.load_installed_metadata(metadata_path.resolve(), require_current_release=False)


def build_elevated_arguments(installation: dict[str, Any]) -> str:
    return subprocess.list2cmdline(
        [
            str(installation["release_broker"]),
            "register-task-com",
            "--metadata",
            str(installation["metadata_path"]),
        ]
    )


def shell_execute_runas(executable: Path, params: str, cwd: Path) -> int:
    return int(
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            str(executable),
            params,
            str(cwd),
            SW_SHOWNORMAL,
        )
    )


def finalize(installation: dict[str, Any]) -> dict[str, Any]:
    task = broker.task_status()
    if not task_ready(task):
        raise RuntimeError("AtStartup + S4U + highest não foi verificado")
    metadata = dict(installation["metadata"])
    metadata.update(
        {
            "activation_pending": False,
            "requires_uac_activation": False,
            "admin_channel_ready": True,
            "uac_activated_at": broker.now_iso(),
        }
    )
    broker.atomic_json(installation["metadata_path"], metadata)
    started = broker.run_task()
    return {"metadata": metadata, "task": task, "start": started}


def launch(metadata_path: Path, *, confirm: str, timeout_seconds: int) -> dict[str, Any]:
    validate_launcher(host=socket.gethostname(), platform=os.name, confirm=confirm)
    installation = load_installation(metadata_path)

    current = broker.task_status()
    if task_ready(current):
        return {"ok": True, "mode": "already_ready", **finalize(installation)}

    if is_admin():
        broker.register_task_from_metadata(installation["metadata_path"])
        return {"ok": True, "mode": "already_elevated", **finalize(installation)}

    rc = shell_execute_runas(
        installation["python_executable"],
        build_elevated_arguments(installation),
        installation["release_root"],
    )
    if rc <= 32:
        raise RuntimeError(f"uac_launch_failed:{rc}")

    deadline = time.monotonic() + max(5, min(timeout_seconds, 120))
    while time.monotonic() < deadline:
        if task_ready(broker.task_status()):
            return {"ok": True, "mode": "uac", **finalize(installation)}
        time.sleep(1.0)
    return {"ok": False, "mode": "uac", "result": "UAC_APPROVAL_OR_PROVISIONING_PENDING"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()
    try:
        result = launch(
            args.metadata or default_metadata_path(),
            confirm=args.confirm,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:1000]}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
