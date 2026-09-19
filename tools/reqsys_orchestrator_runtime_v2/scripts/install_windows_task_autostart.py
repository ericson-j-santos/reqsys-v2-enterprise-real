from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

TASK_FOLDER = r"\Automation"
TASK_NAME = "ReqSysOrchestrator24x7"
TASK_CREATE_OR_UPDATE = 6
TASK_LOGON_S4U = 2
TASK_LOGON_INTERACTIVE_TOKEN = 3
TASK_RUNLEVEL_LUA = 0
TASK_TRIGGER_BOOT = 8
TASK_TRIGGER_LOGON = 9
TASK_TRIGGER_DAILY = 2
TASK_ACTION_EXEC = 0
TASK_INSTANCES_IGNORE_NEW = 2
VALID_LOGON_MODES = {"interactive", "s4u"}


def identity() -> str:
    domain = os.environ.get("USERDOMAIN", "").strip()
    user = os.environ.get("USERNAME", "").strip() or getpass.getuser()
    return f"{domain}\\{user}" if domain else user


def connect():
    import win32com.client

    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    root = service.GetFolder("\\")
    try:
        folder = service.GetFolder(TASK_FOLDER)
    except Exception:
        folder = root.CreateFolder("Automation")
    return service, folder


def configure(
    definition,
    *,
    install_root: Path,
    service_config: Path,
    python_exe: Path,
    start_in_seconds: int,
    logon_mode: str = "interactive",
) -> int:
    if logon_mode not in VALID_LOGON_MODES:
        raise ValueError("unsupported logon_mode")

    definition.RegistrationInfo.Description = (
        "Governed resilient ReqSys orchestrator supervisor"
    )
    settings = definition.Settings
    settings.Enabled = True
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

    logon_type = (
        TASK_LOGON_S4U if logon_mode == "s4u" else TASK_LOGON_INTERACTIVE_TOKEN
    )
    principal = definition.Principal
    principal.UserId = identity()
    principal.LogonType = logon_type
    principal.RunLevel = TASK_RUNLEVEL_LUA

    triggers = definition.Triggers
    if logon_mode == "s4u":
        boot = triggers.Create(TASK_TRIGGER_BOOT)
        boot.Enabled = True
    else:
        logon = triggers.Create(TASK_TRIGGER_LOGON)
        logon.Enabled = True
        logon.UserId = identity()

    daily = triggers.Create(TASK_TRIGGER_DAILY)
    daily.Enabled = True
    daily.StartBoundary = (
        datetime.now().astimezone() + timedelta(seconds=start_in_seconds)
    ).replace(microsecond=0).isoformat()
    daily.DaysInterval = 1
    daily.Repetition.Interval = "PT5M"
    daily.Repetition.Duration = "P1D"
    daily.Repetition.StopAtDurationEnd = False

    action = definition.Actions.Create(TASK_ACTION_EXEC)
    action.Path = str(python_exe)
    action.Arguments = f'-m scripts.service_supervisor --config "{service_config}"'
    action.WorkingDirectory = str(install_root)
    return logon_type


def snapshot(task) -> dict[str, object]:
    definition = task.Definition
    action = definition.Actions.Item(1)
    settings = definition.Settings
    return {
        "path": task.Path,
        "enabled": bool(settings.Enabled),
        "start_when_available": bool(settings.StartWhenAvailable),
        "execution_time_limit": str(settings.ExecutionTimeLimit),
        "multiple_instances": int(settings.MultipleInstances),
        "restart_count": int(settings.RestartCount),
        "restart_interval": str(settings.RestartInterval),
        "principal_logon_type": int(definition.Principal.LogonType),
        "trigger_count": int(definition.Triggers.Count),
        "action_count": int(definition.Actions.Count),
        "action_path": str(action.Path),
        "action_arguments": str(action.Arguments),
        "working_directory": str(action.WorkingDirectory),
    }


def apply(
    *,
    install_root: Path,
    service_config: Path,
    python_exe: Path,
    start_in_seconds: int,
    run_now: bool,
    logon_mode: str = "interactive",
) -> dict[str, object]:
    if not install_root.is_dir():
        raise FileNotFoundError(install_root)
    if not service_config.is_file():
        raise FileNotFoundError(service_config)
    if not (install_root / "scripts" / "service_supervisor.py").is_file():
        raise FileNotFoundError(install_root / "scripts" / "service_supervisor.py")
    if not python_exe.is_file():
        raise FileNotFoundError(python_exe)

    service, folder = connect()
    definition = service.NewTask(0)
    logon_type = configure(
        definition,
        install_root=install_root,
        service_config=service_config,
        python_exe=python_exe,
        start_in_seconds=start_in_seconds,
        logon_mode=logon_mode,
    )
    task = folder.RegisterTaskDefinition(
        TASK_NAME,
        definition,
        TASK_CREATE_OR_UPDATE,
        identity(),
        None,
        logon_type,
    )
    state = snapshot(task)
    expected_args = f'-m scripts.service_supervisor --config "{service_config}"'
    mismatches = {}
    checks = {
        "enabled": True,
        "start_when_available": True,
        "execution_time_limit": "PT0S",
        "multiple_instances": TASK_INSTANCES_IGNORE_NEW,
        "restart_count": 999,
        "restart_interval": "PT1M",
        "principal_logon_type": logon_type,
        "trigger_count": 2,
        "action_count": 1,
        "action_path": str(python_exe),
        "action_arguments": expected_args,
        "working_directory": str(install_root),
    }
    for key, expected in checks.items():
        if state.get(key) != expected:
            mismatches[key] = {"expected": expected, "actual": state.get(key)}
    if mismatches:
        raise RuntimeError("task validation failed: " + json.dumps(mismatches, sort_keys=True))

    instance = None
    if run_now:
        running = task.Run("")
        instance = str(getattr(running, "InstanceGuid", ""))
    return {
        "result": "ORCHESTRATOR_TASK_AUTOSTART_APPLIED",
        "logon_mode": logon_mode,
        "run_now": run_now,
        "running_instance": instance,
        **state,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True)
    parser.add_argument("--service-config", required=True)
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--start-in-seconds", type=int, default=30)
    parser.add_argument(
        "--logon-mode",
        choices=sorted(VALID_LOGON_MODES),
        default="interactive",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--run-now", action="store_true")
    args = parser.parse_args()
    try:
        if not 20 <= args.start_in_seconds <= 120:
            raise ValueError("start-in-seconds must be 20..120")
        if not args.apply:
            print(json.dumps({
                "result": "dry_run",
                "identity": identity(),
                "install_root": args.install_root,
                "service_config": args.service_config,
                "python_exe": args.python_exe,
                "logon_mode": args.logon_mode,
            }, sort_keys=True))
            return 0
        result = apply(
            install_root=Path(args.install_root),
            service_config=Path(args.service_config),
            python_exe=Path(args.python_exe),
            start_in_seconds=args.start_in_seconds,
            run_now=args.run_now,
            logon_mode=args.logon_mode,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            "result": "blocked",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
