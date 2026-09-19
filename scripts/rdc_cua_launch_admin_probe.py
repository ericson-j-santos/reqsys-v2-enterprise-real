#!/usr/bin/env python3
"""Valida se o daemon CUA já elevado pode lançar um helper com token administrativo."""
from __future__ import annotations
import json
import subprocess
import sys
import time
from pathlib import Path

CUA = Path(r"C:\Users\Windows\AppData\Local\Programs\Cua\cua-driver\bin\cua-driver.exe")
RECEIPT = Path(r"C:\dev\chatgpt-workers\artifacts\rdc-cua-admin-probe.json")
SESSION = "rdc-cua-admin-probe"


def main() -> int:
    RECEIPT.unlink(missing_ok=True)
    helper = Path(__file__).resolve().with_name("rdc_cua_admin_probe.py")
    payload = {
        "path": sys.executable,
        "additional_arguments": [str(helper), "--receipt", str(RECEIPT)],
        "start_minimized": True,
    }
    cp = subprocess.run(
        [str(CUA), "call", "launch_app", json.dumps(payload, separators=(",", ":"))],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
        check=False,
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and not RECEIPT.is_file():
        time.sleep(0.5)
    receipt = {}
    if RECEIPT.is_file():
        try:
            receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            receipt = {"receipt_invalid": True}
    result = {
        "launch_exit_code": cp.returncode,
        "launch_stdout": (cp.stdout or "")[:4000],
        "launch_stderr": (cp.stderr or "")[:2000],
        "receipt": receipt,
        "receipt_exists": RECEIPT.is_file(),
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if RECEIPT.is_file() else 2


if __name__ == "__main__":
    raise SystemExit(main())
