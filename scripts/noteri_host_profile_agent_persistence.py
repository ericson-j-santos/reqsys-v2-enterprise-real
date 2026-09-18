#!/usr/bin/env python3
"""Persistência Windows do agente NORMAL/ESTUDO do Noteri.

Instala uma tarefa Task Scheduler AtStartup usando S4U (sem senha), copia os
scripts do agente para um diretório estável em LOCALAPPDATA e registra uma
baseline de boot para validação pós-reinício.
"""
from __future__ import annotations

import argparse
import ctypes
import getpass
import hashlib
import json
import os
import shutil
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASK_NAME = "ReqSys-NoteriHostProfileAgent"
RUN_VALUE_NAME = "ReqSysNoteriHostProfileAgent"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
SERVICE_NAME = "noteri-host-profile-agent"
DEFAULT_PORT = 8765
REBOOT_TOLERANCE_SECONDS = 120

TASK_TRIGGER_BOOT = 8
TASK_ACTION_EXEC = 0
TASK_LOGON_S4U = 2
TASK_CREATE_OR_UPDATE = 6
TASK_RUNLEVEL_LUA = 0
TASK_INSTANCES_IGNORE_NEW = 2


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def runtime_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA não definido")
    return Path(local) / "ReqSys" / "TodoGlobal24x7"


def stable_dir() -> Path:
    return runtime_root() / "noteri-host-profile-agent"


def metadata_path() -> Path:
    return runtime_root() / "noteri-host-profile-autostart.json"


def evidence_path() -> Path:
    return runtime_root() / "noteri-host-profile-postboot.json"


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def windows_boot_epoch() -> int:
    if os.name != "nt":
        raise RuntimeError("validação de boot exige Windows")
    kernel32 = ctypes.windll.kernel32
    kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    uptime_seconds = int(kernel32.GetTickCount64() // 1000)
    return int(time.time()) - uptime_seconds


def reboot_observed(baseline_boot_epoch: int, current_boot_epoch: int) -> bool:
    return abs(current_boot_epoch - baseline_boot_epoch) > REBOOT_TOLERANCE_SECONDS


def current_user_id() -> str:
    computer = socket.gethostname().strip()
    username = getpass.getuser().strip()
    if not computer or not username:
        raise RuntimeError("identidade local indisponível")
    return f"{computer}\\{username}"


def probe_agent(port: int = DEFAULT_PORT, timeout: float = 2.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("ok") is not True or payload.get("service") != SERVICE_NAME:
        return None
    if str(payload.get("host") or "").casefold() != "noteri":
        return None
    if payload.get("loopback_only") is not True:
        return None
    return payload


def _scheduler():
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pywin32 indisponível") from exc
    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    return service


def _winreg():
    if os.name != "nt":
        raise RuntimeError("registro de autostart exige Windows")
    import winreg
    return winreg


def run_key_status() -> dict[str, Any]:
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, value_type = winreg.QueryValueEx(key, RUN_VALUE_NAME)
    except FileNotFoundError:
        return {"configured": False, "value_name": RUN_VALUE_NAME}
    return {
        "configured": bool(str(value).strip()),
        "value_name": RUN_VALUE_NAME,
        "value_type": int(value_type),
    }


def install_user_logon_autostart(command_line: str) -> None:
    winreg = _winreg()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, command_line)


def _is_access_denied(exc: BaseException) -> bool:
    text = repr(exc).casefold()
    return (
        "-2147024891" in text
        or "access is denied" in text
        or "acesso negado" in text
    )


def task_status() -> dict[str, Any]:
    service = _scheduler()
    root = service.GetFolder("\\")
    try:
        task = root.GetTask(TASK_NAME)
    except Exception:
        return {"exists": False, "task_name": TASK_NAME}
    definition = task.Definition
    triggers = []
    for index in range(1, definition.Triggers.Count + 1):
        trigger = definition.Triggers.Item(index)
        triggers.append({"type": int(trigger.Type), "enabled": bool(trigger.Enabled)})
    actions = []
    for index in range(1, definition.Actions.Count + 1):
        action = definition.Actions.Item(index)
        actions.append(
            {
                "type": int(action.Type),
                "path": str(getattr(action, "Path", "") or ""),
                "working_directory": str(getattr(action, "WorkingDirectory", "") or ""),
            }
        )
    return {
        "exists": True,
        "task_name": TASK_NAME,
        "enabled": bool(task.Enabled),
        "state": int(task.State),
        "last_task_result": int(task.LastTaskResult),
        "next_run_time": str(task.NextRunTime),
        "principal_user": str(definition.Principal.UserId or ""),
        "principal_logon_type": int(definition.Principal.LogonType),
        "principal_run_level": int(definition.Principal.RunLevel),
        "triggers": triggers,
        "actions": actions,
    }


def install(repo_root: Path) -> dict[str, Any]:
    if socket.gethostname().casefold() != "noteri":
        raise RuntimeError("instalação permitida somente no host Noteri")
    if os.name != "nt":
        raise RuntimeError("instalação exige Windows")

    scripts_dir = repo_root / "scripts"
    source_agent = scripts_dir / "noteri_host_profile_agent.py"
    source_control = scripts_dir / "noteri_host_profile_agent_control.py"
    if not source_agent.is_file() or not source_control.is_file():
        raise FileNotFoundError("scripts do agente NORMAL/ESTUDO não encontrados")

    target = stable_dir()
    target.mkdir(parents=True, exist_ok=True)
    target_agent = target / source_agent.name
    target_control = target / source_control.name
    shutil.copy2(source_agent, target_agent)
    shutil.copy2(source_control, target_control)

    persistence_mode = "task_at_startup_s4u"
    requires_user_logon = False
    task_registration_error = None
    service = _scheduler()
    root = service.GetFolder("\\")
    definition = service.NewTask(0)
    definition.RegistrationInfo.Description = "ReqSys Noteri NORMAL/ESTUDO local agent autostart"
    definition.Settings.Enabled = True
    definition.Settings.StartWhenAvailable = True
    definition.Settings.DisallowStartIfOnBatteries = False
    definition.Settings.StopIfGoingOnBatteries = False
    definition.Settings.MultipleInstances = TASK_INSTANCES_IGNORE_NEW
    definition.Settings.ExecutionTimeLimit = "PT5M"

    trigger = definition.Triggers.Create(TASK_TRIGGER_BOOT)
    trigger.Enabled = True
    trigger.Delay = "PT20S"

    action = definition.Actions.Create(TASK_ACTION_EXEC)
    action.Path = sys.executable
    action.Arguments = f'"{target_control}" start --host Noteri'
    action.WorkingDirectory = str(target)

    principal = definition.Principal
    principal.UserId = current_user_id()
    principal.LogonType = TASK_LOGON_S4U
    principal.RunLevel = TASK_RUNLEVEL_LUA

    try:
        root.RegisterTaskDefinition(
            TASK_NAME,
            definition,
            TASK_CREATE_OR_UPDATE,
            principal.UserId,
            "",
            TASK_LOGON_S4U,
        )
        registered = root.GetTask(TASK_NAME)
        registered.Run("")
    except Exception as exc:
        if not _is_access_denied(exc):
            raise
        command_line = f'"{sys.executable}" "{target_control}" start --host Noteri'
        install_user_logon_autostart(command_line)
        persistence_mode = "hkcu_run_at_logon"
        requires_user_logon = True
        task_registration_error = "access_denied"

    deadline = time.monotonic() + 12.0
    health = probe_agent()
    while health is None and time.monotonic() < deadline:
        time.sleep(0.25)
        health = probe_agent()

    boot_epoch = windows_boot_epoch()
    metadata = {
        "schema_version": "1",
        "task_name": TASK_NAME,
        "installed_at": now_iso(),
        "host": socket.gethostname(),
        "baseline_boot_epoch": boot_epoch,
        "python": sys.executable,
        "stable_dir": str(target),
        "agent_sha256": sha256_file(target_agent),
        "control_sha256": sha256_file(target_control),
        "s4u": True,
        "password_used": False,
        "run_level": "limited",
        "persistence_mode": persistence_mode,
        "requires_user_logon": requires_user_logon,
        "task_registration_error": task_registration_error,
    }
    atomic_json(metadata_path(), metadata)
    status = task_status()
    run_status = run_key_status()
    task_ok = (
        status.get("exists") is True
        and status.get("principal_logon_type") == TASK_LOGON_S4U
        and any(item.get("type") == TASK_TRIGGER_BOOT for item in status.get("triggers", []))
    )
    persistence_ok = task_ok or run_status.get("configured") is True
    ok = health is not None and persistence_ok
    return {
        "ok": ok,
        "result": "NOTERI_AGENT_AUTOSTART_INSTALLED" if ok else "NOTERI_AGENT_AUTOSTART_INCOMPLETE",
        "health": health,
        "task": status,
        "run_key": run_status,
        "metadata": metadata,
    }


def postboot_check(require_reboot: bool) -> tuple[int, dict[str, Any]]:
    if socket.gethostname().casefold() != "noteri":
        raise RuntimeError("validação permitida somente no host Noteri")
    meta_file = metadata_path()
    if not meta_file.is_file():
        raise RuntimeError("metadata de autostart ausente")
    metadata = json.loads(meta_file.read_text(encoding="utf-8"))
    baseline = int(metadata["baseline_boot_epoch"])
    current = windows_boot_epoch()
    restarted = reboot_observed(baseline, current)
    health = probe_agent()
    task = task_status()
    run_status = run_key_status()
    persistence_present = task.get("exists") is True or run_status.get("configured") is True
    ready = restarted and health is not None and persistence_present
    payload = {
        "schema_version": "1",
        "generated_at": now_iso(),
        "host": socket.gethostname(),
        "baseline_boot_epoch": baseline,
        "current_boot_epoch": current,
        "reboot_observed": restarted,
        "agent_healthy": health is not None,
        "health": health,
        "task": task,
        "run_key": run_status,
        "persistence_present": persistence_present,
        "ready": ready,
    }
    atomic_json(evidence_path(), payload)
    if require_reboot:
        if not restarted:
            return 4, payload
        if health is None:
            return 5, payload
        if not persistence_present:
            return 6, payload
    return 0 if (not require_reboot or ready) else 1, payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Persistência pós-reboot do agente NORMAL/ESTUDO no Noteri")
    sub = parser.add_subparsers(dest="command", required=True)

    install_parser = sub.add_parser("install")
    install_parser.add_argument("--repo-root", type=Path, required=True)

    sub.add_parser("status")

    check_parser = sub.add_parser("postboot-check")
    check_parser.add_argument("--require-reboot", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "install":
            result = install(args.repo_root.resolve())
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["ok"] else 2
        if args.command == "status":
            payload = {
                "ok": True,
                "task": task_status(),
                "run_key": run_key_status(),
                "metadata_exists": metadata_path().is_file(),
                "agent_healthy": probe_agent() is not None,
            }
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 0
        code, payload = postboot_check(args.require_reboot)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return code
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
