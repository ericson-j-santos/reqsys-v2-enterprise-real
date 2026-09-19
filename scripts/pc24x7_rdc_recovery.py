#!/usr/bin/env python3
"""Recover the governed Remote Desktop Commander on the PC24x7 Desktop."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
TASK_HEADLESS = r"\Automation\RemoteDesktopCommanderHeadless"
TASK_INTERACTIVE = r"\Automation\RemoteDesktopCommander"
HEADLESS_RUNNER = Path(r"C:\ProgramData\ReqSys\RdcSvc\rdc-headless-runner.cjs")
INTERACTIVE_LAUNCHER = Path(r"C:\RemoteDesktopCommander\start-remote-desktop-commander.cmd")
HEADLESS_MARKERS = (\n    "// RDC_HEADLESS_V2_PRIMARY_OWNER",\n    "// RDC_HEADLESS_V3_READY_CLAIM",\n)
INTERACTIVE_MARKERS = (
    "REM RDC_LAUNCHER_V3_RESILIENT",
    "REM RDC_LAUNCHER_V4_ARBITRATED",
)
CONFIRM = "RECOVER-GOVERNED-RDC"
ALLOWED_TASKS = (TASK_HEADLESS, TASK_INTERACTIVE)


class RecoveryError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_host() -> str:
    if os.name != "nt":
        raise RecoveryError("Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise RecoveryError(f"host não autorizado: {host}")
    return host


def schtasks_path() -> Path:
    system_root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    target = system_root / "System32" / "schtasks.exe"
    if not target.is_file():
        raise RecoveryError("schtasks.exe não encontrado")
    return target


def task_query(task_name: str) -> subprocess.CompletedProcess[str]:
    if task_name not in ALLOWED_TASKS:
        raise RecoveryError("task_name não allowlisted")
    return subprocess.run(
        [str(schtasks_path()), "/Query", "/TN", task_name, "/FO", "LIST", "/V"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )


def task_run(task_name: str) -> subprocess.CompletedProcess[str]:
    if task_name not in ALLOWED_TASKS:
        raise RecoveryError("task_name não allowlisted")
    return subprocess.run(
        [str(schtasks_path()), "/Run", "/TN", task_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )


def validate_headless_source() -> dict[str, Any]:
    if not HEADLESS_RUNNER.is_file():
        return {"exists": False, "governed": False}
    text = HEADLESS_RUNNER.read_text(encoding="utf-8-sig", errors="replace")
    marker = next((value for value in HEADLESS_MARKERS if value in text), None)\n    return {"exists": True, "governed": marker is not None, "marker": marker}


def validate_interactive_source() -> dict[str, Any]:
    if not INTERACTIVE_LAUNCHER.is_file():
        return {"exists": False, "governed": False}
    text = INTERACTIVE_LAUNCHER.read_text(encoding="utf-8-sig", errors="replace")
    marker = next((value for value in INTERACTIVE_MARKERS if value in text), None)
    return {"exists": True, "governed": marker is not None, "marker": marker}


def task_available(task_name: str) -> bool:
    return task_query(task_name).returncode == 0


def recover(confirm: str, correlation_id: str) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmação inválida")
    host = validate_host()
    headless_source = validate_headless_source()
    interactive_source = validate_interactive_source()
    attempts: list[dict[str, Any]] = []

    if headless_source.get("governed") and task_available(TASK_HEADLESS):
        result = task_run(TASK_HEADLESS)
        attempts.append({"owner": "headless", "task": TASK_HEADLESS, "returncode": result.returncode})
        if result.returncode == 0:
            return {
                "ok": True,
                "host": host,
                "owner": "headless",
                "task": TASK_HEADLESS,
                "correlation_id": correlation_id,
                "attempts": attempts,
                "headless_source": headless_source,
                "interactive_source": interactive_source,
                "production_touched": False,
                "secrets_read": False,
                "observed_at": now_iso(),
            }

    if interactive_source.get("governed") and task_available(TASK_INTERACTIVE):
        result = task_run(TASK_INTERACTIVE)
        attempts.append({"owner": "interactive", "task": TASK_INTERACTIVE, "returncode": result.returncode})
        if result.returncode == 0:
            return {
                "ok": True,
                "host": host,
                "owner": "interactive",
                "task": TASK_INTERACTIVE,
                "correlation_id": correlation_id,
                "attempts": attempts,
                "headless_source": headless_source,
                "interactive_source": interactive_source,
                "production_touched": False,
                "secrets_read": False,
                "observed_at": now_iso(),
            }

    raise RecoveryError(
        "nenhuma tarefa RDC governada pôde ser iniciada; "
        + json.dumps(
            {
                "headless_source": headless_source,
                "interactive_source": interactive_source,
                "attempts": attempts,
            },
            sort_keys=True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    code = 0
    try:
        payload = recover(args.confirm, args.correlation_id)
    except (RecoveryError, OSError, subprocess.SubprocessError) as exc:
        payload = {
            "ok": False,
            "host": socket.gethostname(),
            "correlation_id": args.correlation_id,
            "error": str(exc)[:1000],
            "error_type": type(exc).__name__,
            "production_touched": False,
            "secrets_read": False,
            "observed_at": now_iso(),
        }
        code = 2
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
