#!/usr/bin/env python3
"""Inventário somente leitura das tasks ReqSys em \\Automation."""
from __future__ import annotations

import json

import win32com.client  # type: ignore

FOLDER = r"\Automation"


def main() -> int:
    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    folder = service.GetFolder(FOLDER)
    items = []
    for task in folder.GetTasks(1):
        definition = task.Definition
        principal = definition.Principal
        actions = []
        for action in definition.Actions:
            actions.append(
                {
                    "type": int(action.Type),
                    "path": getattr(action, "Path", None),
                    "arguments": getattr(action, "Arguments", None),
                    "working_directory": getattr(action, "WorkingDirectory", None),
                }
            )
        items.append(
            {
                "name": str(task.Name),
                "enabled": bool(task.Enabled),
                "state": int(task.State),
                "last_result": int(task.LastTaskResult),
                "principal_user": str(principal.UserId or ""),
                "principal_logon_type": int(principal.LogonType),
                "principal_run_level": int(principal.RunLevel),
                "actions": actions,
            }
        )
    print(json.dumps({"folder": FOLDER, "tasks": items}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
