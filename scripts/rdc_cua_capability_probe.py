#!/usr/bin/env python3
"""Probe somente leitura da sintaxe cua-driver call."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

BIN = Path(r"C:\Users\Windows\AppData\Local\Programs\Cua\cua-driver\bin\cua-driver.exe")


def main() -> int:
    cp = subprocess.run(
        [str(BIN), "call", "--help"],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=15,
        check=False,
    )
    print(json.dumps({"exit_code": cp.returncode, "stdout": cp.stdout or "", "stderr": cp.stderr or ""}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
