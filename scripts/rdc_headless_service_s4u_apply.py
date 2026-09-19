#!/usr/bin/env python3
"""Instala o owner headless RDC com conta local dedicada e S4U, sem senha."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import socket
import time
from datetime import datetime, timedelta
from pathlib import Path

HOST = "DESKTOP-PDQK954"
ACCOUNT = "ReqSysRdcSvc"
CONFIRM = "APPLY-DESKTOP-RDC-SERVICE-S4U"
TASK_FOLDER = r"\Automation"
HEADLESS_TASK = "RemoteDesktopCommanderHeadless"
LEGACY_TASK = "RemoteDesktopCommander"
RUNTIME = Path(r"C:\ProgramData\ReqSys\RdcSvc")
RUNNER = RUNTIME / "rdc-headless-runner.cjs"
SERVICE_WRAPPER = RUNTIME / "rdc-headless-service-launcher.cjs"
LOG = RUNTIME / "rdc-headless.log"
TASK_CREATE_OR_UPDATE = 6
TASK_LOGON_S4U = 2
TASK_RUNLEVEL_LUA = 0
TASK_TRIGGER_BOOT = 8
TASK_TRIGGER_DAILY = 2
TASK_ACTION_EXEC = 0
TASK_INSTANCES_IGNORE_NEW = 2
CURRENT_STAGE = {"value": "init"}


def is_admin() -> bool:
    return os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())


def validate(host: str, platform: str, confirm: str) -> None:
    if host.casefold() != HOST.casefold():
        raise RuntimeError("host_not_allowlisted")
    if platform != "nt":
        raise RuntimeError("windows_required")
    if confirm != CONFIRM:
        raise RuntimeError("confirmation_invalid")
    if not is_admin():
        raise RuntimeError("administrative_token_required")


def account_identity() -> tuple[str, object]:
    import win32net
    import win32security

    info = win32net.NetUserGetInfo(None, ACCOUNT, 1)
    if not info:
        raise RuntimeError("service_account_missing")
    sid, _, _ = win32security.LookupAccountName(None, ACCOUNT)
    return f"{socket.gethostname()}\\{ACCOUNT}", sid


def configure_batch_rights(sid: object) -> None:
    import win32security

    required = ("LsaOpenPolicy", "LsaAddAccountRights")
    if not all(hasattr(win32security, name) for name in required):
        raise RuntimeError("lsa_api_unavailable")
    policy = win32security.LsaOpenPolicy(None, win32security.POLICY_ALL_ACCESS)
    win32security.LsaAddAccountRights(
        policy,
        sid,
        (
            "SeBatchLogonRight",
            "SeDenyInteractiveLogonRight",
            "SeDenyRemoteInteractiveLogonRight",
        ),
    )


def grant_runtime_acl(sid: object) -> None:
    import ntsecuritycon
    import win32security

    RUNTIME.mkdir(parents=True, exist_ok=True)
    sd = win32security.GetFileSecurity(
        str(RUNTIME), win32security.DACL_SECURITY_INFORMATION
    )
    dacl = sd.GetSecurityDescriptorDacl()
    if dacl is None:
        dacl = win32security.ACL()
    flags = (
        win32security.OBJECT_INHERIT_ACE
        | win32security.CONTAINER_INHERIT_ACE
    )
    mask = (
        ntsecuritycon.FILE_GENERIC_READ
        | ntsecuritycon.FILE_GENERIC_WRITE
        | ntsecuritycon.FILE_GENERIC_EXECUTE
    )
    dacl.AddAccessAllowedAceEx(win32security.ACL_REVISION_DS, flags, mask, sid)
    sd.SetSecurityDescriptorDacl(1, dacl, 0)
    win32security.SetFileSecurity(
        str(RUNTIME), win32security.DACL_SECURITY_INFORMATION, sd
    )


def secure_session_file(path: Path, service_sid: object) -> None:
    import ntsecuritycon
    import win32security

    system_sid = win32security.CreateWellKnownSid(
        win32security.WinLocalSystemSid, None
    )
    admin_sid = win32security.CreateWellKnownSid(
        win32security.WinBuiltinAdministratorsSid, None
    )
    dacl = win32security.ACL()
    rw = ntsecuritycon.FILE_GENERIC_READ | ntsecuritycon.FILE_GENERIC_WRITE
    full = ntsecuritycon.FILE_ALL_ACCESS
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, rw, service_sid)
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, full, system_sid)
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, full, admin_sid)
    sd = win32security.SECURITY_DESCRIPTOR()
    sd.SetSecurityDescriptorDacl(1, dacl, 0)
    win32security.SetFileSecurity(
        str(path), win32security.DACL_SECURITY_INFORMATION, sd
    )


def prepare_service_profile(service_sid: object) -> Path:
    current_profile = Path(os.environ.get("USERPROFILE", ""))
    source = current_profile / ".desktop-commander-device" / "device.json"
    if not source.is_file():
        raise RuntimeError("source_persisted_session_missing")
    profile = Path(os.environ.get("SystemDrive", "C:")) / "Users" / ACCOUNT
    target_dir = profile / ".desktop-commander-device"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "device.json"
    temp = target.with_suffix(".json.tmp")
    shutil.copy2(source, temp)
    os.replace(temp, target)
    secure_session_file(target, service_sid)
    return profile


def write_service_wrapper(profile: Path) -> None:
    if not RUNNER.is_file():
        raise RuntimeError("governed_headless_runner_missing")
    profile_text = str(profile)
    homepath = profile_text[2:] if len(profile_text) > 2 else "\\"
    content = (
        "// RDC_SERVICE_S4U_PROFILE_V1\n"
        + "process.env.USERPROFILE = " + json.dumps(profile_text) + ";\n"
        + "process.env.HOME = " + json.dumps(profile_text) + ";\n"
        + "process.env.HOMEDRIVE = " + json.dumps(profile.drive or "C:") + ";\n"
        + "process.env.HOMEPATH = " + json.dumps(homepath) + ";\n"
        + "require(" + json.dumps(str(RUNNER)) + ");\n"
    )
    temp = SERVICE_WRAPPER.with_suffix(".tmp")
    temp.write_text(content, encoding="utf-8", newline="")
    os.replace(temp, SERVICE_WRAPPER)


def resolve_node() -> Path:
    candidates = [
        RUNTIME / "bin" / "node.exe",
        Path(r"C:\Program Files\nodejs\node.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    found = shutil.which("node.exe") or shutil.which("node")
    if found:
        return Path(found)
    raise RuntimeError("node_runtime_missing")


def task_service():
    import win32com.client

    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    return service


def ensure_folder(service):
    try:
        return service.GetFolder(TASK_FOLDER)
    except Exception:
        return service.GetFolder("\\").CreateFolder(TASK_FOLDER.strip("\\"))


def register_task(user_id: str, node: Path):
    service = task_service()
    folder = ensure_folder(service)
    definition = service.NewTask(0)
    definition.RegistrationInfo.Description = (
        "ReqSys RDC headless S4U owner - governed watchdog"
    )
    settings = definition.Settings
    settings.Enabled = True
    settings.AllowDemandStart = True
    settings.StartWhenAvailable = True
    settings.DisallowStartIfOnBatteries = False
    settings.StopIfGoingOnBatteries = False
    settings.ExecutionTimeLimit = "PT0S"
    settings.MultipleInstances = TASK_INSTANCES_IGNORE_NEW
    settings.RestartCount = 999
    settings.RestartInterval = "PT1M"
    try:
        settings.RunOnlyIfNetworkAvailable = False
    except Exception:
        pass

    principal = definition.Principal
    principal.UserId = user_id
    principal.LogonType = TASK_LOGON_S4U
    principal.RunLevel = TASK_RUNLEVEL_LUA

    boot = definition.Triggers.Create(TASK_TRIGGER_BOOT)
    boot.Enabled = True

    daily = definition.Triggers.Create(TASK_TRIGGER_DAILY)
    daily.Enabled = True
    daily.StartBoundary = (
        datetime.now().astimezone() + timedelta(seconds=30)
    ).replace(microsecond=0).isoformat()
    daily.DaysInterval = 1
    daily.Repetition.Interval = "PT5M"
    daily.Repetition.Duration = "P1D"
    daily.Repetition.StopAtDurationEnd = False

    action = definition.Actions.Create(TASK_ACTION_EXEC)
    action.Path = str(node)
    action.Arguments = f'"{SERVICE_WRAPPER}"'
    action.WorkingDirectory = str(RUNTIME)

    task = folder.RegisterTaskDefinition(
        HEADLESS_TASK,
        definition,
        TASK_CREATE_OR_UPDATE,
        user_id,
        "",
        TASK_LOGON_S4U,
    )
    return folder, task


def marker_counts() -> dict[str, int]:
    if not LOG.is_file():
        return {"runner": 0, "restored": 0, "ready": 0}
    text = LOG.read_text(encoding="utf-8", errors="replace")
    return {
        "runner": text.count("runner_start mode=primary_owner"),
        "restored": text.count("Session restored"),
        "ready": text.count("Device ready:"),
    }


def wait_for_count(key: str, baseline: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if marker_counts()[key] > baseline:
            return True
        time.sleep(1)
    return False


def apply(confirm: str) -> dict:
    CURRENT_STAGE["value"] = "validate"
    validate(socket.gethostname(), os.name, confirm)

    CURRENT_STAGE["value"] = "account_identity"
    user_id, sid = account_identity()

    CURRENT_STAGE["value"] = "batch_rights"
    configure_batch_rights(sid)

    CURRENT_STAGE["value"] = "runtime_acl"
    grant_runtime_acl(sid)

    CURRENT_STAGE["value"] = "service_profile"
    profile = prepare_service_profile(sid)

    CURRENT_STAGE["value"] = "service_wrapper"
    write_service_wrapper(profile)
    node = resolve_node()

    before = marker_counts()
    CURRENT_STAGE["value"] = "register_task"
    folder, task = register_task(user_id, node)

    CURRENT_STAGE["value"] = "start_task"
    task.Run("")
    if not wait_for_count("runner", before["runner"], 20):
        raise RuntimeError("headless_runner_did_not_start")

    CURRENT_STAGE["value"] = "cutover_legacy"
    legacy_stopped = False
    try:
        legacy = folder.GetTask(LEGACY_TASK)
        if int(legacy.State) == 4:
            legacy.Stop(0)
            legacy_stopped = True
    except Exception:
        pass

    CURRENT_STAGE["value"] = "wait_ready"
    restored = wait_for_count("restored", before["restored"], 60)
    ready = wait_for_count("ready", before["ready"], 20 if restored else 1)
    if not (restored and ready):
        raise RuntimeError("headless_controller_did_not_become_ready")

    CURRENT_STAGE["value"] = "complete"
    counts = marker_counts()
    return {
        "ok": True,
        "host": HOST,
        "service_account": ACCOUNT,
        "password_used": False,
        "logon_type": "S4U",
        "batch_logon_configured": True,
        "interactive_logon_denied": True,
        "remote_interactive_logon_denied": True,
        "session_copied": True,
        "session_acl_restricted": True,
        "task_name": HEADLESS_TASK,
        "task_enabled": bool(task.Enabled),
        "task_state": int(task.State),
        "task_last_result": int(task.LastTaskResult),
        "legacy_task_stopped_for_cutover": legacy_stopped,
        "node_under_programdata": str(node).casefold().startswith(
            str(RUNTIME).casefold()
        ),
        "runner_marker_count": counts["runner"],
        "session_restored_count": counts["restored"],
        "device_ready_count": counts["ready"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        result = apply(args.confirm)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": CURRENT_STAGE.get("value"),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "password_used": False,
                    "secret_value_exposed": False,
                },
                sort_keys=True,
            )
        )
        return 2
    result["secret_value_exposed"] = False
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
