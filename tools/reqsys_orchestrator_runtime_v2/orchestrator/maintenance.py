from __future__ import annotations

import ctypes
import getpass
import hashlib
import json
import os
import re
import socket
import subprocess
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TASK_FOLDER = r"\Automation"
TASK_NAME = "RemoteDesktopCommander"
LAUNCHER = Path(r"C:\RemoteDesktopCommander\start-remote-desktop-commander.cmd")

REBOOT_TASK = "host.reboot.once.v1"
MAX_REBOOT_WINDOW_MINUTES = 15
ACTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")

SHTDN_REASON_MAJOR_APPLICATION = 0x00040000
SHTDN_REASON_MINOR_MAINTENANCE = 0x00000001
SHTDN_REASON_FLAG_PLANNED = 0x80000000
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002
ERROR_NOT_ALL_ASSIGNED = 1300


class MaintenanceError(RuntimeError):
    pass


class LUID(ctypes.Structure):
    _fields_ = [
        ("LowPart", wintypes.DWORD),
        ("HighPart", wintypes.LONG),
    ]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Luid", LUID),
        ("Attributes", wintypes.DWORD),
    ]


class TOKEN_PRIVILEGES_ONE(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", wintypes.DWORD),
        ("Privileges", LUID_AND_ATTRIBUTES * 1),
    ]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat()


def owner_fingerprint() -> str:
    identity = f"{getpass.getuser()}@{socket.gethostname()}".encode(
        "utf-8", errors="replace"
    )
    return hashlib.sha256(identity).hexdigest()


def default_power_config_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "ReqSys" / "CommandGateway" / "owner-host-power-once.local.json"
    return Path.home() / ".reqsys-command-gateway" / "owner-host-power-once.local.json"


def power_audit_path() -> Path:
    return default_power_config_path().parent / "owner-host-power-audit.jsonl"


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def append_power_audit(payload: dict[str, Any]) -> None:
    path = power_audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    try:
        os.write(fd, raw.encode("utf-8"))
    finally:
        os.close(fd)


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise MaintenanceError("invalid authorization timestamp") from exc
    if parsed.tzinfo is None:
        raise MaintenanceError("authorization timestamp must contain timezone")
    return parsed.astimezone(timezone.utc)


def _task_action_snapshot(task) -> dict[str, Any]:
    definition = task.Definition
    if int(definition.Actions.Count) != 1:
        raise MaintenanceError("rdc task action count mismatch")
    action = definition.Actions.Item(1)
    action_path = str(action.Path)
    arguments = str(action.Arguments)
    expected_launcher = str(LAUNCHER).casefold()
    if not action_path.casefold().endswith(r"\system32\cmd.exe"):
        raise MaintenanceError("rdc task executable mismatch")
    if expected_launcher not in arguments.casefold():
        raise MaintenanceError("rdc task launcher mismatch")
    return {
        "path": str(task.Path),
        "enabled": bool(task.Enabled),
        "state": int(task.State),
        "last_task_result": int(task.LastTaskResult),
        "action_path": action_path,
        "launcher": str(LAUNCHER),
    }


def _launcher_exists() -> bool:
    return LAUNCHER.is_file()


def _connect_task():
    try:
        import win32com.client
    except ImportError as exc:
        raise MaintenanceError("pywin32 unavailable") from exc

    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    folder = service.GetFolder(TASK_FOLDER)
    return folder.GetTask(TASK_NAME)


def recover_rdc(*, target_host: str | None = None) -> dict[str, Any]:
    local_host = socket.gethostname()
    if target_host and target_host.casefold() != local_host.casefold():
        raise MaintenanceError("target_host does not match local host")
    if not _launcher_exists():
        raise MaintenanceError("rdc launcher missing")

    task = _connect_task()
    before = _task_action_snapshot(task)
    if not before["enabled"]:
        raise MaintenanceError("rdc task disabled")

    running = task.Run("")
    after = _task_action_snapshot(task)
    return {
        "handler": "host.rdc.recover.v1",
        "host": local_host,
        "task": str(task.Path),
        "launcher": str(LAUNCHER),
        "before": before,
        "after": after,
        "running_instance": str(getattr(running, "InstanceGuid", "")),
    }


def load_reboot_authorization(
    *,
    action_id: str,
    target_host: str,
    config_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(action_id, str) or not ACTION_ID_RE.fullmatch(action_id):
        raise MaintenanceError("invalid action_id")
    local_host = socket.gethostname()
    if not isinstance(target_host, str) or target_host.casefold() != local_host.casefold():
        raise MaintenanceError("target_host does not match local host")

    path = config_path or default_power_config_path()
    if not path.is_file():
        raise MaintenanceError("owner reboot authorization missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaintenanceError("owner reboot authorization invalid") from exc

    if payload.get("version") != 1 or payload.get("enabled") is not True:
        raise MaintenanceError("owner reboot authorization disabled")
    if payload.get("action_id") != action_id:
        raise MaintenanceError("action_id does not match owner authorization")
    if payload.get("operation") != "reboot":
        raise MaintenanceError("owner authorization is not for reboot")
    if str(payload.get("host", "")).casefold() != local_host.casefold():
        raise MaintenanceError("owner authorization belongs to another host")
    if payload.get("scope") != f"host://{local_host}/reboot-once":
        raise MaintenanceError("owner authorization scope mismatch")
    if payload.get("owner_fingerprint") != owner_fingerprint():
        raise MaintenanceError("owner authorization fingerprint mismatch")
    if payload.get("consumed_at"):
        raise MaintenanceError("owner reboot authorization already consumed")

    authorized_at = parse_utc(payload.get("authorized_at"))
    expires_at = parse_utc(payload.get("expires_at"))
    if expires_at - authorized_at > timedelta(
        minutes=MAX_REBOOT_WINDOW_MINUTES, seconds=5
    ):
        raise MaintenanceError("owner reboot authorization window exceeds limit")
    reference = now or utc_now()
    if expires_at <= reference:
        raise MaintenanceError("owner reboot authorization expired")
    return payload


def consume_reboot_authorization(
    *,
    payload: dict[str, Any],
    correlation_id: str,
    config_path: Path | None = None,
) -> dict[str, Any]:
    path = config_path or default_power_config_path()
    consumed = dict(payload)
    consumed["consumed_at"] = utc_iso()
    consumed["correlation_id"] = correlation_id
    atomic_json(path, consumed)
    append_power_audit(
        {
            "schema_version": "1.0.0",
            "event": "owner_host_power_consumed",
            "action_id": consumed["action_id"],
            "host": consumed["host"],
            "operation": "reboot",
            "correlation_id": correlation_id,
            "timestamp": consumed["consumed_at"],
            "executor": "orchestrator-maintenance-adapter",
        }
    )
    return consumed


def _set_windows_last_error(value: int) -> None:
    setter = getattr(ctypes, "set_last_error", None)
    if setter is not None:
        setter(value)


def _get_windows_last_error() -> int:
    getter = getattr(ctypes, "get_last_error", None)
    return int(getter()) if getter is not None else 0


def _planned_reboot_reason() -> int:
    return (
        SHTDN_REASON_MAJOR_APPLICATION
        | SHTDN_REASON_MINOR_MAINTENANCE
        | SHTDN_REASON_FLAG_PLANNED
    )


def _windows_shutdown_api():
    if os.name != "nt":
        raise MaintenanceError("local reboot is supported only on Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.LookupPrivilegeValueW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.POINTER(LUID),
    ]
    advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
    advapi32.AdjustTokenPrivileges.argtypes = [
        wintypes.HANDLE,
        wintypes.BOOL,
        ctypes.POINTER(TOKEN_PRIVILEGES_ONE),
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL
    advapi32.InitiateSystemShutdownExW.argtypes = [
        wintypes.LPWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    advapi32.InitiateSystemShutdownExW.restype = wintypes.BOOL
    return kernel32, advapi32


def _enable_shutdown_privilege(kernel32, advapi32) -> None:
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(token),
    ):
        raise MaintenanceError(
            f"OpenProcessToken failed win32={_get_windows_last_error()}"
        )
    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(
            None, "SeShutdownPrivilege", ctypes.byref(luid)
        ):
            raise MaintenanceError(
                f"LookupPrivilegeValueW failed win32={_get_windows_last_error()}"
            )
        privileges = TOKEN_PRIVILEGES_ONE()
        privileges.PrivilegeCount = 1
        privileges.Privileges[0].Luid = luid
        privileges.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        _set_windows_last_error(0)
        if not advapi32.AdjustTokenPrivileges(
            token, False, ctypes.byref(privileges), 0, None, None
        ):
            raise MaintenanceError(
                f"AdjustTokenPrivileges failed win32={_get_windows_last_error()}"
            )
        error = _get_windows_last_error()
        if error == ERROR_NOT_ALL_ASSIGNED:
            raise MaintenanceError("SeShutdownPrivilege is not assigned to local user")
        if error != 0:
            raise MaintenanceError(f"AdjustTokenPrivileges returned win32={error}")
    finally:
        kernel32.CloseHandle(token)


def _submit_local_reboot(delay_seconds: int) -> subprocess.CompletedProcess[str]:
    if (
        not isinstance(delay_seconds, int)
        or isinstance(delay_seconds, bool)
        or delay_seconds < 5
        or delay_seconds > 60
    ):
        raise MaintenanceError("delay_seconds must be between 5 and 60")
    kernel32, advapi32 = _windows_shutdown_api()
    _enable_shutdown_privilege(kernel32, advapi32)
    _set_windows_last_error(0)
    accepted = advapi32.InitiateSystemShutdownExW(
        None,
        "ReqSys governed one-time reboot validation",
        delay_seconds,
        False,
        True,
        _planned_reboot_reason(),
    )
    if not accepted:
        error = _get_windows_last_error()
        return subprocess.CompletedProcess(
            ["InitiateSystemShutdownExW"],
            error or 1,
            stdout="",
            stderr=f"win32={error}",
        )
    return subprocess.CompletedProcess(
        ["InitiateSystemShutdownExW"],
        0,
        stdout="accepted",
        stderr="",
    )


def reboot_once(
    *,
    action_id: str,
    target_host: str,
    correlation_id: str,
    delay_seconds: int = 10,
    config_path: Path | None = None,
) -> dict[str, Any]:
    payload = load_reboot_authorization(
        action_id=action_id,
        target_host=target_host,
        config_path=config_path,
    )

    consume_reboot_authorization(
        payload=payload,
        correlation_id=correlation_id,
        config_path=config_path,
    )
    completed = _submit_local_reboot(delay_seconds)
    append_power_audit(
        {
            "schema_version": "1.0.0",
            "event": "owner_host_power_submitted",
            "action_id": action_id,
            "host": payload["host"],
            "operation": "reboot",
            "correlation_id": correlation_id,
            "returncode": completed.returncode,
            "stdout_sha256": hashlib.sha256(
                completed.stdout.encode("utf-8", errors="replace")
            ).hexdigest(),
            "stderr_sha256": hashlib.sha256(
                completed.stderr.encode("utf-8", errors="replace")
            ).hexdigest(),
            "timestamp": utc_iso(),
            "executor": "orchestrator-maintenance-adapter",
        }
    )
    if completed.returncode != 0:
        raise MaintenanceError(
            f"governed local reboot failed with exit={completed.returncode}"
        )
    return {
        "handler": REBOOT_TASK,
        "action_id": action_id,
        "host": payload["host"],
        "operation": "reboot",
        "correlation_id": correlation_id,
        "delay_seconds": delay_seconds,
        "consumed": True,
    }
