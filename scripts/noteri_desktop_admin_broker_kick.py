#!/usr/bin/env python3
"""Solicita pelo Noteri somente o start da tarefa existente do Desktop Admin Broker."""
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

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
TASK_NAME = r"\Automation\ReqSysDesktopAdminBroker"
CONFIRM = "KICK-EXISTING-DESKTOP-ADMIN-BROKER"
CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


class KickError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())[:limit]


def require_noteri(host: str | None = None, platform: str | None = None) -> None:
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise KickError(f"host_origem_nao_autorizado:{actual_host}")
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
    source_host: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise KickError("confirmation_invalid")
    require_noteri(source_host, platform)

    argv = [
        str(schtasks_executable()),
        "/Run",
        "/S",
        TARGET_HOST,
        "/TN",
        TASK_NAME,
    ]
    completed = run_cmd(argv)
    payload = {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "task_name": TASK_NAME,
        "run_returncode": int(completed.returncode),
        "run_requested": completed.returncode == 0,
        "task_created_or_modified": False,
        "credentials_supplied": False,
        "secrets_read": False,
        "production_touched": False,
        "reboot_performed": False,
    }
    if completed.returncode == 0:
        payload.update({"ok": True, "result": "EXISTING_DESKTOP_ADMIN_BROKER_RUN_REQUESTED"})
    else:
        payload.update({
            "ok": False,
            "result": "DESKTOP_ADMIN_BROKER_RUN_BLOCKED",
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
        default=Path("artifacts/noteri-desktop-admin-broker-kick/evidence.json"),
    )
    args = parser.parse_args()
    try:
        result = kick(confirm=args.confirm, evidence_file=args.evidence_file.resolve())
    except (KickError, OSError, subprocess.SubprocessError) as exc:
        result = {
            "schema_version": "1",
            "generated_at_utc": now_iso(),
            "ok": False,
            "result": "NOTERI_DESKTOP_ADMIN_BROKER_KICK_BLOCKED",
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
