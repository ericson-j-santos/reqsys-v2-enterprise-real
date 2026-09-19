from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

TASK_FOLDER = r"\Automation"
TASK_NAME = "RemoteDesktopCommander"
LAUNCHER = Path(r"C:\RemoteDesktopCommander\start-remote-desktop-commander.cmd")


class MaintenanceError(RuntimeError):
    pass


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
