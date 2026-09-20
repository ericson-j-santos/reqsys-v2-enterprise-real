#!/usr/bin/env python3
"""Prova fail-closed do plano de controle alternativo no Noteri."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
CONFIRM = "PROBE-NOTERI-CONTROL-PLANE"


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


def tasklist_path() -> Path:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    target = root / "System32" / "tasklist.exe"
    if not target.is_file():
        raise ProbeError("tasklist.exe não encontrado")
    return target


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
    return {
        "ok": True,
        "host": host,
        "runner_name": runner_name,
        "runner_os": runner_os,
        "runner_arch": runner_arch or None,
        "runner_listener_detected": True,
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
