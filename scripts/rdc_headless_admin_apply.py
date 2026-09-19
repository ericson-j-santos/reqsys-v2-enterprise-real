#!/usr/bin/env python3
"""Aplicador administrativo governado do watchdog RDC headless no Desktop."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

HOST = "DESKTOP-PDQK954"
RECEIPT = Path(r"C:\ProgramData\ReqSys\RdcSvc\headless-install-receipt.json")
CONFIRM = "APPLY-DESKTOP-RDC-HEADLESS"


def is_admin() -> bool:
    return os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())


def git_head(root: Path) -> str:
    cp = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if cp.returncode != 0:
        raise RuntimeError("rules_git_head_unavailable")
    return cp.stdout.strip().lower()


def run_json(command: list[str], *, cwd: Path, timeout: int = 180) -> dict:
    cp = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    line = (cp.stdout or "").strip().splitlines()
    payload = {}
    if line:
        try:
            payload = json.loads(line[-1])
        except json.JSONDecodeError:
            payload = {}
    if cp.returncode != 0:
        detail = str(
            payload.get("error")
            or payload.get("reason")
            or payload.get("error_type")
            or payload.get("result")
            or "unknown"
        )
        raise RuntimeError(
            "governed_admin_step_failed:"
            + str(cp.returncode)
            + ":"
            + str(payload.get("stage") or "unknown_stage")
            + ":"
            + detail[:500]
        )
    return payload


def write_receipt(payload: dict) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    safe = dict(payload)
    safe["secret_value_exposed"] = False
    tmp = RECEIPT.with_suffix(".tmp")
    tmp.write_text(json.dumps(safe, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, RECEIPT)


def apply(rules_root: Path, expected_rules_sha: str, confirm: str) -> dict:
    if socket.gethostname().casefold() != HOST.casefold():
        raise RuntimeError("host_not_allowlisted")
    if os.name != "nt":
        raise RuntimeError("windows_required")
    if confirm != CONFIRM:
        raise RuntimeError("confirmation_invalid")
    if not is_admin():
        raise RuntimeError("administrative_token_required")

    rules_root = rules_root.resolve()
    expected = expected_rules_sha.strip().lower()
    if len(expected) != 40 or git_head(rules_root) != expected:
        raise RuntimeError("rules_sha_mismatch")

    arbitration = run_json(
        [sys.executable, str(rules_root / "scripts" / "rdc_owner_arbitration.py"), "--apply"],
        cwd=rules_root,
    )
    if arbitration.get("result") not in {"OWNER_ARBITRATION_APPLIED", "already_applied"}:
        raise RuntimeError("owner_arbitration_not_proven")

    service_apply = run_json(
        [
            sys.executable,
            str(Path(__file__).resolve().with_name("rdc_headless_service_s4u_apply.py")),
            "--confirm",
            "APPLY-DESKTOP-RDC-SERVICE-S4U",
        ],
        cwd=Path(__file__).resolve().parents[1],
        timeout=120,
    )
    if service_apply.get("ok") is not True:
        raise RuntimeError("headless_service_task_not_proven")

    result = {
        "ok": True,
        "host": HOST,
        "rules_sha": expected,
        "owner_arbitration": arbitration.get("result"),
        "task_result": "RDC_HEADLESS_SERVICE_S4U_READY",
        "headless": True,
        "requires_user_logon": False,
        "start_requested": True,
        "principal_logon_type": "S4U",
        "service_account": service_apply.get("service_account"),
        "password_used": False,
        "session_restored_count": service_apply.get("session_restored_count"),
        "device_ready_count": service_apply.get("device_ready_count"),
        "legacy_task_stopped_for_cutover": service_apply.get("legacy_task_stopped_for_cutover"),
    }
    write_receipt(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules-root", type=Path, required=True)
    parser.add_argument("--expected-rules-sha", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        result = apply(args.rules_root, args.expected_rules_sha, args.confirm)
    except Exception as exc:
        result = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
        try:
            write_receipt(result)
        except OSError:
            pass
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
