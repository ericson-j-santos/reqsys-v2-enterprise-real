#!/usr/bin/env python3
"""Launcher UAC governado para habilitar AtStartup do supervisor Codex PC24x7."""
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
from typing import Any

import codex_pc24x7_supervisor as supervisor

LAUNCH_CONFIRM = "LAUNCH-CODEX-PC24X7-HEADLESS-UAC"
SW_SHOWNORMAL = 1


def validate_launcher(*, host: str, platform: str, confirm: str) -> None:
    if host.casefold() != supervisor.EXPECTED_HOST.casefold():
        raise RuntimeError(f"launcher permitido somente no host {supervisor.EXPECTED_HOST}")
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
    return supervisor.default_runtime_root() / "metadata.json"


def task_headless_ready(task: dict[str, Any]) -> bool:
    return (
        task.get("exists") is True
        and task.get("trigger_at_startup") is True
        and str(task.get("logon_type") or "").casefold() == "s4u"
    )


def load_installation(metadata_path: Path) -> dict[str, Any]:
    if not metadata_path.is_file():
        raise RuntimeError("metadata do supervisor ausente")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    runtime_root = Path(str(metadata.get("runtime_root") or "")).resolve()
    release_root = Path(str(metadata.get("release_root") or "")).resolve()
    python_executable = Path(str(metadata.get("python_executable") or "")).resolve()
    source_sha = str(metadata.get("source_sha") or "")
    if len(source_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in source_sha):
        raise RuntimeError("source_sha da instalação inválido")
    if release_root.parent != runtime_root / "releases":
        raise RuntimeError("release_root fora do runtime governado")
    release_supervisor = release_root / "scripts" / "codex_pc24x7_supervisor.py"
    launcher = runtime_root / "run.py"
    for path, label in (
        (release_supervisor, "supervisor instalado"),
        (python_executable, "Python do backend"),
        (launcher, "launcher estável"),
    ):
        if not path.is_file():
            raise RuntimeError(f"{label} ausente: {path}")
    return {
        "metadata": metadata,
        "metadata_path": metadata_path,
        "runtime_root": runtime_root,
        "release_root": release_root,
        "release_supervisor": release_supervisor,
        "python_executable": python_executable,
        "launcher": launcher,
        "source_sha": source_sha,
    }


def build_elevated_arguments(installation: dict[str, Any]) -> str:
    argv = [
        str(installation["release_supervisor"]),
        "register-task-com",
        "--python-executable",
        str(installation["python_executable"]),
        "--launcher",
        str(installation["launcher"]),
    ]
    return subprocess.list2cmdline(argv)


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


def finalize_headless(installation: dict[str, Any]) -> dict[str, Any]:
    task = supervisor.task_status()
    if not task_headless_ready(task):
        raise RuntimeError("AtStartup S4U não foi verificado")
    metadata = dict(installation["metadata"])
    metadata.update(
        {
            "persistence_mode": "task_at_startup_no_password",
            "requires_user_logon": False,
            "task_registration_error": None,
            "headless_24x7": True,
            "headless_enabled_at": supervisor.now_iso(),
        }
    )
    supervisor.atomic_json(installation["metadata_path"], metadata)
    supervisor._remove_run_key()
    return {"metadata": metadata, "task": task, "run_key": supervisor.run_key_status()}


def launch(metadata_path: Path, *, confirm: str, timeout_seconds: int) -> dict[str, Any]:
    validate_launcher(host=socket.gethostname(), platform=os.name, confirm=confirm)
    installation = load_installation(metadata_path.resolve())

    current = supervisor.task_status()
    if task_headless_ready(current):
        finalized = finalize_headless(installation)
        return {
            "ok": True,
            "mode": "already_ready",
            "result": "CODEX_PC24X7_HEADLESS_READY",
            **finalized,
        }

    if is_admin():
        supervisor.register_task_com(
            python_executable=installation["python_executable"],
            launcher=installation["launcher"],
        )
        finalized = finalize_headless(installation)
        return {
            "ok": True,
            "mode": "already_elevated",
            "result": "CODEX_PC24X7_HEADLESS_PROVISIONED",
            **finalized,
        }

    rc = shell_execute_runas(
        Path(sys.executable).resolve(),
        build_elevated_arguments(installation),
        installation["release_root"],
    )
    if rc <= 32:
        raise RuntimeError(f"uac_launch_failed:{rc}")

    deadline = time.monotonic() + max(5, min(timeout_seconds, 120))
    while time.monotonic() < deadline:
        task = supervisor.task_status()
        if task_headless_ready(task):
            finalized = finalize_headless(installation)
            return {
                "ok": True,
                "mode": "uac",
                "result": "CODEX_PC24X7_HEADLESS_PROVISIONED",
                **finalized,
            }
        time.sleep(1.0)

    return {
        "ok": False,
        "mode": "uac",
        "result": "UAC_APPROVAL_OR_PROVISIONING_PENDING",
        "task": supervisor.task_status(),
        "run_key": supervisor.run_key_status(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Provisiona AtStartup do Codex PC24x7 via UAC")
    parser.add_argument("--metadata", type=Path, default=None)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()
    try:
        result = launch(
            args.metadata or default_metadata_path(),
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
