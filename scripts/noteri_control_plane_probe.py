#!/usr/bin/env python3
"""Prova fail-closed do plano de controle alternativo no Noteri."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
CONFIRM = "PROBE-NOTERI-CONTROL-PLANE"
TASK_NAME = r"\Automation\ReqSysNoteriControlPlaneWatchdog"
RUNTIME_DIR = Path("ReqSys") / "NoteriControlPlaneWatchdog"
INTERACTIVE_RESULT = "interactive-launch-result.json"
ELEVATED_RESULT = "elevated-install-result.json"


class ProbeError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_host() -> str:
    if os.name != "nt":
        raise ProbeError("Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise ProbeError(f"host não autorizado: {host}")
    return host


def runtime_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise ProbeError("LOCALAPPDATA ausente")
    return Path(local) / RUNTIME_DIR


def system32_path(name: str) -> Path:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    target = root / "System32" / name
    if not target.is_file():
        raise ProbeError(f"{name} não encontrado")
    return target


def tasklist_path() -> Path:
    return system32_path("tasklist.exe")


def schtasks_path() -> Path:
    return system32_path("schtasks.exe")


def runner_listener_detected() -> bool:
    completed = subprocess.run(
        [str(tasklist_path()), "/FI", "IMAGENAME eq Runner.Listener.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    return completed.returncode == 0 and "runner.listener.exe" in completed.stdout.casefold()


def decode_xml(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8", errors="replace")


def parse_task_xml(raw: bytes) -> dict[str, Any]:
    root = ET.fromstring(decode_xml(raw))
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    enabled_text = (
        root.findtext("./t:Settings/t:Enabled", default="true", namespaces=ns) or "true"
    ).strip()
    logon_type = (
        root.findtext("./t:Principals/t:Principal/t:LogonType", default="", namespaces=ns) or ""
    ).strip()
    boot = root.find("./t:Triggers/t:BootTrigger", ns) is not None
    return {
        "exists": True,
        "enabled": enabled_text.casefold() == "true",
        "trigger_at_startup": boot,
        "logon_type": logon_type,
        "validator": "schtasks_xml",
    }


def task_status() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [str(schtasks_path()), "/Query", "/TN", TASK_NAME, "/XML"],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if completed.returncode != 0:
            return {
                "exists": False,
                "error": "task_not_found_or_query_failed",
                "validator": "schtasks_xml",
            }
        return parse_task_xml(completed.stdout)
    except (OSError, ET.ParseError, UnicodeError, subprocess.SubprocessError) as exc:
        return {
            "exists": False,
            "error": type(exc).__name__,
            "validator": "schtasks_xml",
        }


def task_headless_ready(task: dict[str, Any]) -> bool:
    return (
        task.get("exists") is True
        and task.get("enabled") is True
        and task.get("trigger_at_startup") is True
        and str(task.get("logon_type") or "").casefold() == "s4u"
    )


def _sanitized_result(path: Path, allowed: set[str]) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        return {"exists": True, "valid": False, "error_type": type(exc).__name__}
    if not isinstance(raw, dict):
        return {"exists": True, "valid": False, "error_type": "invalid_payload"}
    payload: dict[str, Any] = {"exists": True, "valid": True}
    for key in allowed:
        if key in raw:
            value = raw[key]
            if key == "error" and value is not None:
                payload[key] = str(value)[:500]
            else:
                payload[key] = value
    return payload


def activation_diagnostic() -> dict[str, Any]:
    root = runtime_root()
    return {
        "interactive": _sanitized_result(
            root / INTERACTIVE_RESULT,
            {
                "ok",
                "exit_code",
                "source_sha",
                "result",
                "error_type",
                "error",
                "observed_at",
            },
        ),
        "elevated": _sanitized_result(
            root / ELEVATED_RESULT,
            {
                "ok",
                "error_type",
                "error",
                "runtime_ok",
                "activation_pending",
                "requires_uac_activation",
                "headless_persistence",
            },
        ),
    }


def probe(confirm: str, correlation_id: str) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise ProbeError("confirmação inválida")
    correlation_id = correlation_id.strip()
    if not 8 <= len(correlation_id) <= 160:
        raise ProbeError("correlation_id inválido")
    host = validate_host()
    runner_name = str(os.environ.get("RUNNER_NAME") or "").strip()
    runner_os = str(os.environ.get("RUNNER_OS") or "").strip()
    runner_arch = str(os.environ.get("RUNNER_ARCH") or "").strip()
    if not runner_name:
        raise ProbeError("RUNNER_NAME ausente")
    if runner_os.casefold() != "windows":
        raise ProbeError("RUNNER_OS divergente")
    if not runner_listener_detected():
        raise ProbeError("Runner.Listener.exe não comprovado")

    task = task_status()
    return {
        "ok": True,
        "host": host,
        "runner_name": runner_name,
        "runner_os": runner_os,
        "runner_arch": runner_arch or None,
        "runner_listener_detected": True,
        "headless_task": task,
        "headless_ready": task_headless_ready(task),
        "activation_diagnostic": activation_diagnostic(),
        "correlation_id": correlation_id,
        "rdc_required": False,
        "production_touched": False,
        "secrets_read": False,
        "observed_at": now_iso(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    code = 0
    try:
        payload = probe(args.confirm, args.correlation_id)
    except (ProbeError, OSError, subprocess.SubprocessError) as exc:
        payload = {
            "ok": False,
            "host": socket.gethostname(),
            "correlation_id": args.correlation_id,
            "error": str(exc)[:1000],
            "error_type": type(exc).__name__,
            "rdc_required": False,
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
