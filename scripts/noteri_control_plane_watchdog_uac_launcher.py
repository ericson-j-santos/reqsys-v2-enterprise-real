#!/usr/bin/env python3
"""Launcher UAC governado para persistência headless do control plane no Noteri."""
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

import noteri_control_plane_watchdog as watchdog

LAUNCH_CONFIRM = "LAUNCH-NOTERI-CONTROL-PLANE-WATCHDOG-UAC"
SW_SHOWNORMAL = 1


class LauncherError(RuntimeError):
    pass


def validate_launcher(*, host: str, platform: str, confirm: str) -> None:
    if host.casefold() != watchdog.EXPECTED_HOST.casefold():
        raise LauncherError(f"launcher permitido somente no host {watchdog.EXPECTED_HOST}")
    if platform != "nt":
        raise LauncherError("launcher UAC exige Windows")
    if confirm != LAUNCH_CONFIRM:
        raise LauncherError("confirmação UAC inválida")


def is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def load_metadata(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise LauncherError(f"metadata ausente: {resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if str(payload.get("host") or "").casefold() != watchdog.EXPECTED_HOST.casefold():
        raise LauncherError("metadata pertence a host diferente")
    runner_home = Path(str(payload.get("runner_home") or "")).resolve()
    watchdog.validate_runner_home(runner_home)
    return payload


def task_status() -> dict[str, Any]:
    try:
        service = watchdog._scheduler()
        root = service.GetFolder("\\")
        task = root.GetTask(watchdog.TASK_NAME)
        definition = task.Definition
        trigger_types = [
            int(definition.Triggers.Item(index).Type)
            for index in range(1, int(definition.Triggers.Count) + 1)
        ]
        principal = definition.Principal
        return {
            "exists": True,
            "enabled": bool(definition.Settings.Enabled),
            "trigger_at_startup": watchdog.TASK_TRIGGER_BOOT in trigger_types,
            "logon_type": "S4U"
            if int(principal.LogonType) == watchdog.TASK_LOGON_S4U
            else str(int(principal.LogonType)),
            "run_level": int(principal.RunLevel),
        }
    except Exception as exc:
        return {"exists": False, "error": type(exc).__name__}


def task_headless_ready(task: dict[str, Any]) -> bool:
    return (
        task.get("exists") is True
        and task.get("enabled") is True
        and task.get("trigger_at_startup") is True
        and str(task.get("logon_type") or "").casefold() == "s4u"
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


def build_install_args(*, repo_root: Path, runner_home: Path, source_sha: str) -> str:
    argv = [
        str(repo_root / "scripts" / "noteri_control_plane_watchdog.py"),
        "install",
        "--repo-root",
        str(repo_root),
        "--runner-home",
        str(runner_home),
        "--source-sha",
        source_sha,
        "--confirm",
        watchdog.INSTALL_CONFIRM,
    ]
    return subprocess.list2cmdline(argv)


def finalize(metadata_path: Path, task: dict[str, Any]) -> dict[str, Any]:
    metadata = load_metadata(metadata_path)
    metadata.update(
        {
            "task": task,
            "activation_pending": False,
            "requires_uac_activation": False,
            "headless_persistence": True,
            "runtime_persistent_after_login": True,
            "headless_activated_at": watchdog.now_iso(),
        }
    )
    watchdog.atomic_json(metadata_path, metadata)
    runner_home = Path(str(metadata["runner_home"])).resolve()
    cycle = watchdog.cycle(runner_home)
    return {"metadata": metadata, "cycle": cycle}


def launch(
    *,
    repo_root: Path,
    source_sha: str,
    metadata_path: Path,
    confirm: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    validate_launcher(host=socket.gethostname(), platform=os.name, confirm=confirm)
    source_sha = watchdog.validate_source_sha(source_sha)
    repo_root = repo_root.resolve()
    watchdog_source = repo_root / "scripts" / "noteri_control_plane_watchdog.py"
    if not watchdog_source.is_file():
        raise LauncherError("watchdog fonte ausente no checkout")

    metadata = load_metadata(metadata_path)
    runner_home = Path(str(metadata["runner_home"])).resolve()

    current = task_status()
    if task_headless_ready(current):
        finalized = finalize(metadata_path, current)
        return {
            "ok": True,
            "mode": "already_ready",
            "result": "NOTERI_CONTROL_PLANE_HEADLESS_READY",
            "task": current,
            "rdc_required": False,
            "production_touched": False,
            "reboot_performed": False,
            **finalized,
        }

    if is_admin():
        result = subprocess.run(
            [
                sys.executable,
                str(watchdog_source),
                "install",
                "--repo-root",
                str(repo_root),
                "--runner-home",
                str(runner_home),
                "--source-sha",
                source_sha,
                "--confirm",
                watchdog.INSTALL_CONFIRM,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise LauncherError(f"watchdog_install_failed:{result.returncode}")
    else:
        rc = shell_execute_runas(
            Path(sys.executable),
            build_install_args(
                repo_root=repo_root,
                runner_home=runner_home,
                source_sha=source_sha,
            ),
            repo_root,
        )
        if rc <= 32:
            raise LauncherError(f"uac_launch_failed:{rc}")

    deadline = time.monotonic() + max(15, min(timeout_seconds, 240))
    last = current
    while time.monotonic() < deadline:
        last = task_status()
        if task_headless_ready(last):
            finalized = finalize(metadata_path, last)
            return {
                "ok": True,
                "mode": "elevated" if is_admin() else "uac",
                "result": "NOTERI_CONTROL_PLANE_HEADLESS_PROVISIONED",
                "task": last,
                "rdc_required": False,
                "production_touched": False,
                "reboot_performed": False,
                **finalized,
            }
        time.sleep(1)

    return {
        "ok": False,
        "mode": "uac",
        "result": "UAC_APPROVAL_OR_PROVISIONING_PENDING",
        "task": last,
        "rdc_required": False,
        "production_touched": False,
        "reboot_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--metadata", type=Path, default=watchdog.metadata_path())
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()
    try:
        payload = launch(
            repo_root=args.repo_root,
            source_sha=args.source_sha,
            metadata_path=args.metadata,
            confirm=args.confirm,
            timeout_seconds=args.timeout_seconds,
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        watchdog.WatchdogError,
        LauncherError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc)[:1000],
                    "error_type": type(exc).__name__,
                    "rdc_required": False,
                    "production_touched": False,
                    "reboot_performed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
