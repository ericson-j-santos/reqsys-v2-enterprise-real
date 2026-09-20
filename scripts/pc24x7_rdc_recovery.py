#!/usr/bin/env python3
"""Recover the governed Remote Desktop Commander on the PC24x7 Desktop."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
TASK_HEADLESS = r"\Automation\RemoteDesktopCommanderHeadless"
TASK_INTERACTIVE = r"\Automation\RemoteDesktopCommander"
HEADLESS_RUNNER = Path(r"C:\ProgramData\ReqSys\RdcSvc\rdc-headless-runner.cjs")
HEADLESS_CLAIM = Path(r"C:\ProgramData\ReqSys\RdcSvc\rdc-headless-owner.json")
INTERACTIVE_LAUNCHER = Path(r"C:\RemoteDesktopCommander\start-remote-desktop-commander.cmd")
HEADLESS_TRANSPORT_MARKER = "// RDC_HEADLESS_V4_TRANSPORT_GUARD"
HEADLESS_MARKERS = (
    "// RDC_HEADLESS_V2_PRIMARY_OWNER",
    "// RDC_HEADLESS_V3_READY_CLAIM",
    HEADLESS_TRANSPORT_MARKER,
)
HEADLESS_CLAIM_MAX_AGE_SECONDS = 8.0
HEADLESS_READY_TIMEOUT_SECONDS = 12.0
HEADLESS_READY_POLL_SECONDS = 0.5
INTERACTIVE_MARKERS = (
    "REM RDC_LAUNCHER_V3_RESILIENT",
    "REM RDC_LAUNCHER_V4_ARBITRATED",
    "REM RDC_LAUNCHER_V5_READY_CLAIM",
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


def task_end(task_name: str) -> subprocess.CompletedProcess[str]:
    if task_name not in ALLOWED_TASKS:
        raise RecoveryError("task_name não allowlisted")
    return subprocess.run(
        [str(schtasks_path()), "/End", "/TN", task_name],
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


def restart_task(task_name: str) -> dict[str, int]:
    end_result = task_end(task_name)
    run_result = task_run(task_name)
    return {
        "end_returncode": end_result.returncode,
        "run_returncode": run_result.returncode,
    }


def validate_headless_source() -> dict[str, Any]:
    if not HEADLESS_RUNNER.is_file():
        return {"exists": False, "governed": False}
    text = HEADLESS_RUNNER.read_text(encoding="utf-8-sig", errors="replace")
    marker = next((value for value in HEADLESS_MARKERS if value in text), None)
    return {"exists": True, "governed": marker is not None, "marker": marker}


def validate_interactive_source() -> dict[str, Any]:
    if not INTERACTIVE_LAUNCHER.is_file():
        return {"exists": False, "governed": False}
    text = INTERACTIVE_LAUNCHER.read_text(encoding="utf-8-sig", errors="replace")
    marker = next((value for value in INTERACTIVE_MARKERS if value in text), None)
    return {"exists": True, "governed": marker is not None, "marker": marker}


def task_available(task_name: str) -> bool:
    return task_query(task_name).returncode == 0


def read_headless_claim() -> dict[str, Any]:
    if not HEADLESS_CLAIM.is_file():
        return {"fresh": False, "reason": "claim_missing"}
    try:
        payload = json.loads(HEADLESS_CLAIM.read_text(encoding="utf-8"))
        if payload.get("ready") is not True:
            return {"fresh": False, "reason": "claim_not_ready"}
        raw_updated = str(payload.get("updated_at") or "")
        updated = datetime.fromisoformat(raw_updated.replace("Z", "+00:00"))
        if updated.tzinfo is None:
            raise ValueError("updated_at sem timezone")
        age_seconds = (datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds()
        fresh = 0 <= age_seconds <= HEADLESS_CLAIM_MAX_AGE_SECONDS
        return {
            "fresh": fresh,
            "ready": True,
            "age_seconds": round(age_seconds, 3),
            "pid": payload.get("pid"),
            "reason": "fresh" if fresh else "claim_stale",
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"fresh": False, "reason": "claim_invalid", "error_type": type(exc).__name__}


def wait_for_headless_ready(
    timeout_seconds: float = HEADLESS_READY_TIMEOUT_SECONDS,
    poll_seconds: float = HEADLESS_READY_POLL_SECONDS,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = read_headless_claim()
    while not last.get("fresh") and time.monotonic() < deadline:
        time.sleep(poll_seconds)
        last = read_headless_claim()
    return last


def clear_headless_claim() -> dict[str, Any]:
    try:
        HEADLESS_CLAIM.unlink(missing_ok=True)
        return {"cleared": True}
    except OSError as exc:
        return {"cleared": False, "error_type": type(exc).__name__}


def recover(confirm: str, correlation_id: str) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmação inválida")
    host = validate_host()
    headless_source = validate_headless_source()
    interactive_source = validate_interactive_source()
    attempts: list[dict[str, Any]] = []
    headless_ready = False
    headless_claim: dict[str, Any] = {"fresh": False, "reason": "not_attempted"}
    transport_guarded = headless_source.get("marker") == HEADLESS_TRANSPORT_MARKER

    if headless_source.get("governed") and task_available(TASK_HEADLESS):
        if transport_guarded:
            restart = restart_task(TASK_HEADLESS)
            attempt = {"owner": "headless", "task": TASK_HEADLESS, "action": "restart", **restart}
            attempts.append(attempt)
            if restart["run_returncode"] == 0:
                headless_claim = wait_for_headless_ready()
                attempt["transport_claim"] = headless_claim
                headless_ready = bool(headless_claim.get("fresh"))
        else:
            end_result = task_end(TASK_HEADLESS)
            claim_cleanup = clear_headless_claim()
            attempts.append(
                {
                    "owner": "headless",
                    "task": TASK_HEADLESS,
                    "action": "suppress_unverified_transport_owner",
                    "end_returncode": end_result.returncode,
                    "claim_cleanup": claim_cleanup,
                }
            )
            headless_claim = {
                "fresh": False,
                "reason": "transport_guard_required",
                "marker": headless_source.get("marker"),
            }

    interactive_started = False
    if interactive_source.get("governed") and task_available(TASK_INTERACTIVE):
        restart = restart_task(TASK_INTERACTIVE)
        attempts.append(
            {
                "owner": "interactive",
                "task": TASK_INTERACTIVE,
                "action": "ensure_fallback",
                **restart,
            }
        )
        interactive_started = restart["run_returncode"] == 0

    if interactive_started:
        owner = "headless" if headless_ready else "interactive"
        mode = (
            "headless_transport_proven_with_interactive_standby"
            if headless_ready
            else "interactive_fallback"
        )
        return {
            "ok": True,
            "host": host,
            "owner": owner,
            "mode": mode,
            "task": TASK_HEADLESS if headless_ready else TASK_INTERACTIVE,
            "correlation_id": correlation_id,
            "attempts": attempts,
            "headless_source": headless_source,
            "headless_transport_guarded": transport_guarded,
            "headless_claim": headless_claim,
            "interactive_source": interactive_source,
            "fallback_armed": True,
            "production_touched": False,
            "secrets_read": False,
            "observed_at": now_iso(),
        }

    raise RecoveryError(
        "fallback interativo RDC governado não pôde ser iniciado; "
        + json.dumps(
            {
                "headless_source": headless_source,
                "headless_transport_guarded": transport_guarded,
                "headless_claim": headless_claim,
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
