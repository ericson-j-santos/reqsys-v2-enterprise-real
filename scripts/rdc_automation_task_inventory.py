#!/usr/bin/env python3
"""Inventário somente leitura de tasks potencialmente reutilizáveis para RDC/ReqSys."""
from __future__ import annotations

import json
import win32com.client  # type: ignore

KEYWORDS = ("reqsys", "remote", "desktop", "rdc", "automation", "controller", "gateway", "worker", "command")


def scan(folder, path: str, out: list[dict]) -> None:
    try:
        tasks = folder.GetTasks(1)
    except Exception:
        tasks = []
    for task in tasks:
        try:
            d = task.Definition
            p = d.Principal
            actions = []
            hay = [str(task.Name), path, str(p.UserId or "")]
            for action in d.Actions:
                item = {
                    "type": int(action.Type),
                    "path": getattr(action, "Path", None),
                    "arguments": getattr(action, "Arguments", None),
                    "working_directory": getattr(action, "WorkingDirectory", None),
                }
                actions.append(item)
                hay.extend(str(v or "") for v in item.values())
            text = " ".join(hay).casefold()
            if int(p.RunLevel) == 1 or any(k in text for k in KEYWORDS):
                out.append({
                    "folder": path,
                    "name": str(task.Name),
                    "enabled": bool(task.Enabled),
                    "state": int(task.State),
                    "last_result": int(task.LastTaskResult),
                    "principal_user": str(p.UserId or ""),
                    "principal_logon_type": int(p.LogonType),
                    "principal_run_level": int(p.RunLevel),
                    "actions": actions,
                })
        except Exception:
            continue
    try:
        children = folder.GetFolders(0)
    except Exception:
        children = []
    for child in children:
        child_path = (path.rstrip("\\") + "\\" + str(child.Name)) if path != "\\" else "\\" + str(child.Name)
        scan(child, child_path, out)


def main() -> int:
    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    out: list[dict] = []
    scan(service.GetFolder("\\"), "\\", out)
    print(json.dumps({"tasks": out}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
