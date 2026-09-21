#!/usr/bin/env python3
"""Watchdog local do runner GitHub Actions no Noteri, independente de RDC."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

try:
    import winreg
except ModuleNotFoundError:  # pragma: no cover - disponível apenas no Windows
    winreg = None
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
TASK_FOLDER = r"\Automation"
TASK_LEAF_NAME = "ReqSysNoteriControlPlaneWatchdog"
TASK_NAME = rf"{TASK_FOLDER}\{TASK_LEAF_NAME}"
SERVICE_NAME = "reqsys-noteri-control-plane-watchdog"
INSTALL_CONFIRM = "INSTALL-NOTERI-CONTROL-PLANE-WATCHDOG"
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
TASK_TRIGGER_BOOT = 8
TASK_ACTION_EXEC = 0
TASK_LOGON_S4U = 2
TASK_CREATE_OR_UPDATE = 6
TASK_RUNLEVEL_LUA = 0
TASK_INSTANCES_IGNORE_NEW = 2
DEFAULT_INTERVAL_SECONDS = 15
RUN_KEY = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
RUN_VALUE = "ReqSysNoteriControlPlaneWatchdog"


class WatchdogError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def runtime_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise WatchdogError("LOCALAPPDATA não definido")
    return Path(base) / "ReqSys" / "NoteriControlPlaneWatchdog"


def state_path() -> Path:
    return runtime_root() / "state.json"


def metadata_path() -> Path:
    return runtime_root() / "metadata.json"


def require_noteri() -> str:
    if os.name != "nt":
        raise WatchdogError("Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise WatchdogError(f"host não autorizado: {host}")
    return host


def validate_source_sha(value: str) -> str:
    value = value.strip()
    if not SHA_RE.fullmatch(value):
        raise WatchdogError("source_sha deve ser SHA completo")
    return value.lower()


def validate_runner_home(path: Path) -> Path:
    root = path.resolve()
    required = [root / ".runner", root / "run.cmd", root / "bin" / "Runner.Listener.exe"]
    if not all(item.is_file() for item in required):
        raise WatchdogError("runner_home não atende contrato local")
    return root


def tasklist_path() -> Path:
    target = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "tasklist.exe"
    if not target.is_file():
        raise WatchdogError("tasklist.exe não encontrado")
    return target


def runner_running() -> bool:
    result = subprocess.run(
        [str(tasklist_path()), "/FI", "IMAGENAME eq Runner.Listener.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    return result.returncode == 0 and "runner.listener.exe" in result.stdout.casefold()


def start_runner(runner_home: Path, timeout_seconds: float = 15.0) -> bool:
    root = validate_runner_home(runner_home)
    comspec = Path(os.environ.get("ComSpec") or r"C:\Windows\System32\cmd.exe")
    if not comspec.is_file():
        raise WatchdogError("cmd.exe não encontrado")
    subprocess.Popen(
        [str(comspec), "/d", "/c", str(root / "run.cmd")],
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        close_fds=True,
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if runner_running():
            return True
        time.sleep(0.5)
    return runner_running()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def cycle(runner_home: Path) -> dict[str, Any]:
    host = require_noteri()
    root = validate_runner_home(runner_home)
    before = runner_running()
    started = False
    if not before:
        started = start_runner(root)
    after = runner_running()
    payload = {
        "ok": bool(after),
        "service": SERVICE_NAME,
        "host": host,
        "runner_home": str(root),
        "runner_running_before": before,
        "runner_start_attempted": not before,
        "runner_started": started,
        "runner_running_after": after,
        "rdc_required": False,
        "production_touched": False,
        "secrets_read": False,
        "reboot_performed": False,
        "observed_at": now_iso(),
    }
    atomic_json(state_path(), payload)
    return payload


def _scheduler():
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise WatchdogError("pywin32 indisponível") from exc
    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    return service


def ensure_task_folder(service):
    root = service.GetFolder("\\")
    try:
        return service.GetFolder(TASK_FOLDER)
    except Exception:
        return root.CreateFolder(TASK_FOLDER.lstrip("\\"))


def whoami_path() -> Path:
    target = Path(os.environ.get("SystemRoot") or r"C:\\Windows") / "System32" / "whoami.exe"
    if not target.is_file():
        raise WatchdogError("whoami.exe não encontrado")
    return target


def current_principal_candidates() -> list[tuple[str, str]]:
    completed = subprocess.run(
        [str(whoami_path()), "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    candidates: list[tuple[str, str]] = []
    if completed.returncode == 0 and completed.stdout.strip():
        try:
            row = next(csv.reader([completed.stdout.strip()]))
        except (csv.Error, StopIteration):
            row = []
        if len(row) >= 2:
            account = row[0].strip()
            sid = row[1].strip()
            if sid:
                candidates.append(("sid", sid))
            if account:
                candidates.append(("whoami", account))

    if not candidates:
        fallback = subprocess.run(
            [str(whoami_path())],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        account = fallback.stdout.strip() if fallback.returncode == 0 else ""
        if account:
            candidates.append(("whoami", account))

    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for source, value in candidates:
        key = value.casefold()
        if key and key not in seen:
            seen.add(key)
            unique.append((source, value))
    if not unique:
        raise WatchdogError("identidade Windows atual indisponível")
    return unique


def _task_definition(
    service,
    *,
    python_executable: str,
    release_script: Path,
    runner_home: Path,
    principal_id: str,
):
    definition = service.NewTask(0)
    definition.RegistrationInfo.Description = "ReqSys Noteri control-plane watchdog"
    definition.Settings.Enabled = True
    definition.Settings.StartWhenAvailable = True
    definition.Settings.MultipleInstances = TASK_INSTANCES_IGNORE_NEW
    definition.Settings.RestartCount = 5
    definition.Settings.RestartInterval = "PT1M"
    trigger = definition.Triggers.Create(TASK_TRIGGER_BOOT)
    trigger.Enabled = True
    action = definition.Actions.Create(TASK_ACTION_EXEC)
    action.Path = python_executable
    action.Arguments = subprocess.list2cmdline(
        [str(release_script), "watch", "--runner-home", str(runner_home)]
    )
    action.WorkingDirectory = str(release_script.parent)
    principal = definition.Principal
    principal.LogonType = TASK_LOGON_S4U
    principal.RunLevel = TASK_RUNLEVEL_LUA
    principal.UserId = principal_id
    return definition


def register_task(*, python_executable: str, release_script: Path, runner_home: Path) -> dict[str, Any]:
    service = _scheduler()
    folder = ensure_task_folder(service)
    failures: list[str] = []
    for source, principal_id in current_principal_candidates():
        definition = _task_definition(
            service,
            python_executable=python_executable,
            release_script=release_script,
            runner_home=runner_home,
            principal_id=principal_id,
        )
        try:
            folder.RegisterTaskDefinition(
                TASK_LEAF_NAME,
                definition,
                TASK_CREATE_OR_UPDATE,
                principal_id,
                "",
                TASK_LOGON_S4U,
            )
            return {
                "exists": True,
                "trigger": "AtStartup",
                "logon": "S4U",
                "run_level": "limited",
                "principal_source": source,
            }
        except Exception as exc:
            code = getattr(exc, "hresult", None)
            failures.append(f"{source}:{code if code is not None else type(exc).__name__}")
    raise WatchdogError("falha ao registrar S4U para identidade atual: " + ",".join(failures))


def install_logon_fallback(*, python_executable: str, release_script: Path, runner_home: Path) -> dict[str, Any]:
    if winreg is None:
        raise WatchdogError("winreg indisponível fora do Windows")
    command = subprocess.list2cmdline(
        [
            python_executable,
            str(release_script),
            "watch",
            "--runner-home",
            str(runner_home),
        ]
    )
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
    return {
        "exists": True,
        "trigger": "AtLogon",
        "scope": "HKCU",
        "value_name": RUN_VALUE,
        "headless": False,
    }


def install(repo_root: Path, runner_home: Path, source_sha: str, confirm: str) -> dict[str, Any]:
    if confirm != INSTALL_CONFIRM:
        raise WatchdogError("confirmação inválida")
    host = require_noteri()
    sha = validate_source_sha(source_sha)
    runner = validate_runner_home(runner_home)
    source = repo_root.resolve() / "scripts" / "noteri_control_plane_watchdog.py"
    if not source.is_file():
        raise WatchdogError("script fonte ausente")
    release_dir = runtime_root() / "releases" / sha / "scripts"
    release_dir.mkdir(parents=True, exist_ok=True)
    release_script = release_dir / source.name
    shutil.copy2(source, release_script)
    digest = hashlib.sha256(release_script.read_bytes()).hexdigest()
    activation_pending = False
    task: dict[str, Any]
    logon_fallback: dict[str, Any] | None = None
    try:
        task = register_task(
            python_executable=sys.executable,
            release_script=release_script,
            runner_home=runner,
        )
    except Exception as exc:
        text = repr(exc).casefold()
        if "-2147024891" in text or "access is denied" in text or "acesso negado" in text:
            activation_pending = True
            task = {"exists": False, "error": "access_denied"}
            logon_fallback = install_logon_fallback(
                python_executable=sys.executable,
                release_script=release_script,
                runner_home=runner,
            )
        else:
            raise
    metadata = {
        "schema_version": "1",
        "service": SERVICE_NAME,
        "host": host,
        "source_sha": sha,
        "release_script": str(release_script),
        "release_sha256": digest,
        "runner_home": str(runner),
        "task": task,
        "logon_fallback": logon_fallback,
        "runtime_persistent_after_login": bool(logon_fallback) or not activation_pending,
        "headless_persistence": not activation_pending,
        "activation_pending": activation_pending,
        "requires_uac_activation": activation_pending,
        "rdc_required": False,
        "production_touched": False,
        "secrets_read": False,
        "installed_at": now_iso(),
    }
    atomic_json(metadata_path(), metadata)
    current = cycle(runner)
    return {
        "ok": current["ok"] and not activation_pending,
        "runtime_ok": current["ok"],
        "activation_pending": activation_pending,
        "requires_uac_activation": activation_pending,
        "task": task,
        "logon_fallback": logon_fallback,
        "runtime_persistent_after_login": bool(logon_fallback) or not activation_pending,
        "headless_persistence": not activation_pending,
        "state": current,
        "metadata": metadata,
    }


def watch(runner_home: Path, interval_seconds: int) -> int:
    require_noteri()
    validate_runner_home(runner_home)
    interval = max(5, min(interval_seconds, 300))
    while True:
        cycle(runner_home)
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    install_parser = sub.add_parser("install")
    install_parser.add_argument("--repo-root", type=Path, required=True)
    install_parser.add_argument("--runner-home", type=Path, required=True)
    install_parser.add_argument("--source-sha", required=True)
    install_parser.add_argument("--confirm", required=True)
    install_parser.add_argument("--result-path", type=Path)
    cycle_parser = sub.add_parser("cycle")
    cycle_parser.add_argument("--runner-home", type=Path, required=True)
    watch_parser = sub.add_parser("watch")
    watch_parser.add_argument("--runner-home", type=Path, required=True)
    watch_parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    args = parser.parse_args()
    try:
        if args.command == "install":
            payload = install(args.repo_root, args.runner_home, args.source_sha, args.confirm)
            if args.result_path:
                atomic_json(args.result_path.resolve(), payload)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 0 if payload.get("ok") else 3
        if args.command == "cycle":
            payload = cycle(args.runner_home)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 0 if payload.get("ok") else 2
        return watch(args.runner_home, args.interval_seconds)
    except Exception as exc:
        payload = {
            "ok": False,
            "error": str(exc)[:1000],
            "error_type": type(exc).__name__,
            "rdc_required": False,
            "production_touched": False,
            "reboot_performed": False,
        }
        if getattr(args, "command", None) == "install" and getattr(args, "result_path", None):
            try:
                atomic_json(args.result_path.resolve(), payload)
            except Exception:
                pass
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
