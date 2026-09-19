#!/usr/bin/env python3
"""Launcher UAC governado para o watchdog RDC headless do Desktop."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HOST = "DESKTOP-PDQK954"
LAUNCH_CONFIRM = "LAUNCH-DESKTOP-RDC-HEADLESS-UAC"
APPLY_CONFIRM = "APPLY-DESKTOP-RDC-HEADLESS"
RECEIPT = Path(r"C:\ProgramData\ReqSys\RdcSvc\headless-install-receipt.json")
SW_SHOWNORMAL = 1


def validate(host: str, platform: str, confirm: str) -> None:
    if host.casefold() != HOST.casefold():
        raise RuntimeError("host_not_allowlisted")
    if platform != "nt":
        raise RuntimeError("windows_required")
    if confirm != LAUNCH_CONFIRM:
        raise RuntimeError("confirmation_invalid")


def build_args(rules_root: Path, expected_rules_sha: str) -> str:
    helper = Path(__file__).resolve().with_name("rdc_headless_admin_apply.py")
    return subprocess.list2cmdline(
        [
            str(helper),
            "--rules-root",
            str(rules_root.resolve()),
            "--expected-rules-sha",
            expected_rules_sha,
            "--confirm",
            APPLY_CONFIRM,
        ]
    )


def read_receipt() -> dict:
    if not RECEIPT.is_file():
        return {}
    try:
        return json.loads(RECEIPT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def launch(rules_root: Path, expected_rules_sha: str, confirm: str, timeout: int) -> dict:
    validate(socket.gethostname(), os.name, confirm)
    RECEIPT.unlink(missing_ok=True)
    rc = int(
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            build_args(rules_root, expected_rules_sha),
            str(Path(__file__).resolve().parent),
            SW_SHOWNORMAL,
        )
    )
    if rc <= 32:
        raise RuntimeError(f"uac_launch_failed:{rc}")

    deadline = time.monotonic() + max(10, min(timeout, 120))
    while time.monotonic() < deadline:
        receipt = read_receipt()
        if receipt:
            return {
                "ok": receipt.get("ok") is True,
                "mode": "uac",
                "receipt": receipt,
            }
        time.sleep(1)

    return {"ok": False, "mode": "uac", "result": "UAC_APPROVAL_OR_EXECUTION_PENDING"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules-root", type=Path, required=True)
    parser.add_argument("--expected-rules-sha", required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()
    try:
        result = launch(
            args.rules_root,
            args.expected_rules_sha,
            args.confirm,
            args.timeout_seconds,
        )
    except Exception as exc:
        result = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
