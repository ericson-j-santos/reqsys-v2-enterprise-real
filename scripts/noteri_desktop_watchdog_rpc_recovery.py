#!/usr/bin/env python3
"""Recupera a tarefa watchdog já existente do Desktop a partir do Noteri."""
from __future__ import annotations

import argparse
import json
import locale
import os
import socket
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
TASK_NAME = r"\Automation\ReqSysDesktopControlPlaneWatchdog"
CONFIRM = "RUN-EXISTING-DESKTOP-WATCHDOG"
TASK_LOGON_S4U = "S4U"
TCP_PORTS = (135, 445)
CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


class RecoveryError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())[:limit]


def require_noteri(host: str | None = None, platform: str | None = None) -> None:
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise RecoveryError(f"host_origem_nao_autorizado:{actual_host}")
    if actual_platform != "nt":
        raise RecoveryError("windows_required")


def schtasks_executable() -> Path:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    path = root / "System32" / "schtasks.exe"
    if not path.is_file():
        raise RecoveryError("schtasks_not_found")
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


def tcp_probe(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def parse_task_xml(xml_text: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RecoveryError("task_xml_invalid") from exc
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    return {
        "exists": True,
        "trigger_at_startup": root.find(".//t:BootTrigger", ns) is not None,
        "logon_type": root.findtext(
            ".//t:Principal/t:LogonType",
            default="",
            namespaces=ns,
        ),
    }


def query_task(run_cmd: CommandRunner) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None]:
    completed = run_cmd(
        [
            str(schtasks_executable()),
            "/Query",
            "/S",
            TARGET_HOST,
            "/TN",
            TASK_NAME,
            "/XML",
        ]
    )
    if completed.returncode != 0:
        return completed, None
    return completed, parse_task_xml(completed.stdout)


def request_task_run(run_cmd: CommandRunner) -> subprocess.CompletedProcess[str]:
    return run_cmd(
        [
            str(schtasks_executable()),
            "/Run",
            "/S",
            TARGET_HOST,
            "/TN",
            TASK_NAME,
        ]
    )


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def recover(
    *,
    confirm: str,
    evidence_file: Path,
    run_cmd: CommandRunner = default_run,
    probe: Callable[[str, int], bool] = tcp_probe,
    source_host: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    require_noteri(source_host, platform)

    network = {f"tcp_{port}": bool(probe(TARGET_HOST, port)) for port in TCP_PORTS}
    query, task = query_task(run_cmd)
    payload: dict[str, Any] = {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "task_name": TASK_NAME,
        "network": network,
        "query_returncode": int(query.returncode),
        "task": task,
        "run_requested": False,
        "production_touched": False,
        "secrets_read": False,
        "credentials_supplied": False,
        "task_created_or_modified": False,
    }

    if query.returncode != 0 or task is None:
        payload.update(
            {
                "ok": False,
                "result": "DESKTOP_WATCHDOG_QUERY_BLOCKED",
                "query_error": sanitize(query.stderr or query.stdout),
            }
        )
        write_evidence(evidence_file, payload)
        return payload

    if (
        not task.get("trigger_at_startup")
        or str(task.get("logon_type") or "").casefold() != TASK_LOGON_S4U.casefold()
    ):
        payload.update(
            {
                "ok": False,
                "result": "DESKTOP_WATCHDOG_CONFIGURATION_NOT_READY",
            }
        )
        write_evidence(evidence_file, payload)
        return payload

    requested = request_task_run(run_cmd)
    payload["run_returncode"] = int(requested.returncode)
    if requested.returncode != 0:
        payload.update(
            {
                "ok": False,
                "result": "DESKTOP_WATCHDOG_RUN_BLOCKED",
                "run_error": sanitize(requested.stderr or requested.stdout),
            }
        )
        write_evidence(evidence_file, payload)
        return payload

    payload.update(
        {
            "ok": True,
            "result": "EXISTING_DESKTOP_WATCHDOG_RUN_REQUESTED",
            "run_requested": True,
        }
    )
    write_evidence(evidence_file, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("artifacts/noteri-desktop-watchdog-recovery/evidence.json"),
    )
    args = parser.parse_args()
    try:
        result = recover(
            confirm=args.confirm,
            evidence_file=args.evidence_file.resolve(),
        )
    except (RecoveryError, OSError, subprocess.SubprocessError) as exc:
        blocked = {
            "schema_version": "1",
            "generated_at_utc": now_iso(),
            "ok": False,
            "result": "NOTERI_DESKTOP_WATCHDOG_RECOVERY_BLOCKED",
            "error": sanitize(exc),
            "production_touched": False,
            "secrets_read": False,
            "credentials_supplied": False,
            "task_created_or_modified": False,
        }
        write_evidence(args.evidence_file.resolve(), blocked)
        print(json.dumps(blocked, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
