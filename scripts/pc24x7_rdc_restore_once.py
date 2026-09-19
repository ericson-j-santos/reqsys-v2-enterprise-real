#!/usr/bin/env python3
"""One-shot recovery of the pre-existing governed RDC task on PC24x7 Windows."""
from __future__ import annotations

import hashlib
import json
import subprocess
import time

TASKS = (
    r"\Automation\RemoteDesktopCommanderHeadless",
    r"\Automation\RemoteDesktopCommander",
)


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=30,
        check=False,
    )


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def evidence(task: str, action: str, cp: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return {
        "task": task,
        "action": action,
        "exit_code": cp.returncode,
        "stdout_sha256": digest(cp.stdout),
        "stderr_sha256": digest(cp.stderr),
    }


def main() -> int:
    attempts: list[dict[str, object]] = []
    for task in TASKS:
        query = run(["schtasks.exe", "/Query", "/TN", task])
        attempts.append(evidence(task, "query", query))
        if query.returncode != 0:
            continue

        trigger = run(["schtasks.exe", "/Run", "/TN", task])
        attempts.append(evidence(task, "run", trigger))
        if trigger.returncode != 0:
            continue

        time.sleep(12)
        verify = run(["schtasks.exe", "/Query", "/TN", task])
        attempts.append(evidence(task, "verify", verify))
        print(json.dumps({
            "ok": verify.returncode == 0,
            "result": "rdc_task_triggered",
            "selected_task": task,
            "attempts": attempts,
            "production_touched": False,
            "secrets_exposed": False,
        }, sort_keys=True))
        return 0 if verify.returncode == 0 else 4

    print(json.dumps({
        "ok": False,
        "result": "rdc_task_unavailable_or_trigger_failed",
        "attempts": attempts,
        "production_touched": False,
        "secrets_exposed": False,
    }, sort_keys=True))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
