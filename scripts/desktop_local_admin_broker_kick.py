#!/usr/bin/env python3
"""Solicita localmente o start da tarefa existente do Desktop Admin Broker."""
from __future__ import annotations

import argparse
import json
import locale
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

EXPECTED_HOST = "DESKTOP-PDQK954"
TASK_NAME = r"\Automation\ReqSysDesktopAdminBroker"
CONFIRM = "KICK-LOCAL-DESKTOP-ADMIN-BROKER"
CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


class KickError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())[:limit]


def require_desktop(host: str | None = None, platform: str | None = None) -> None:
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_host.casefold() != EXPECTED_HOST.casefold():
        raise KickError(f"host_nao_autorizado:{actual_host}")
    if actual_platform != "nt":
        raise KickError("windows_required")


def schtasks_executable() -> Path:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    path = root / "System32" / "schtasks.exe"
    if not path.is_file():
        raise KickError("schtasks_not_found")
    return path


def default_run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False) or "utf-8",
        errors="replace",
        timeout=25,
        check=False,
    )


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def kick(
    *,
    confirm: str,
    evidence_file: Path,
    run_cmd: CommandRunner = default_run,
    host: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise KickError("confirmation_invalid")
    require_desktop(host, platform)

    argv = [str(schtasks_executable()), "/Run", "/TN", TASK_NAME]
    completed = run_cmd(argv)
    payload = {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "host": EXPECTED_HOST,
        "task_name": TASK_NAME,
        "execution_mode": "local",
        "run_returncode": int(completed.returncode),
        "run_requested": completed.returncode == 0,
        "task_created_or_modified": False,
        "credentials_supplied": False,
        "secrets_read": False,
        "production_touched": False,
        "reboot_performed": False,
    }
    if completed.returncode == 0:
        payload.update({"ok": True, "result": "EXISTING_DESKTOP_ADMIN_BROKER_LOCAL_RUN_REQUESTED"})
    else:
        payload.update({
            "ok": False,
            "result": "DESKTOP_ADMIN_BROKER_LOCAL_RUN_BLOCKED",
            "run_error": sanitize(completed.stderr or completed.stdout),
        })
    write_evidence(evidence_file, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("artifacts/desktop-local-admin-broker-kick/evidence.json"),
    )
    args = parser.parse_args()
    try:
        result = kick(confirm=args.confirm, evidence_file=args.evidence_file.resolve())
    except (KickError, OSError, subprocess.SubprocessError) as exc:
        result = {
            "schema_version": "1",
            "generated_at_utc": now_iso(),
            "ok": False,
            "result": "DESKTOP_LOCAL_ADMIN_BROKER_KICK_BLOCKED",
            "error": sanitize(exc),
            "task_created_or_modified": False,
            "credentials_supplied": False,
            "secrets_read": False,
            "production_touched": False,
            "reboot_performed": False,
        }
        write_evidence(args.evidence_file.resolve(), result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
