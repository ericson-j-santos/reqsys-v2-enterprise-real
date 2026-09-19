#!/usr/bin/env python3
"""Probe somente leitura do CUA driver já instalado."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

BIN = Path(r"C:\Users\Windows\AppData\Local\Programs\Cua\cua-driver\bin\cua-driver.exe")


def main() -> int:
    out = {"exists": BIN.is_file(), "path": str(BIN)}
    if not BIN.is_file():
        print(json.dumps(out, sort_keys=True))
        return 0
    out["sha256"] = hashlib.sha256(BIN.read_bytes()).hexdigest()
    for args, key in [(["--help"], "help"), (["serve", "--help"], "serve_help")]:
        cp = subprocess.run([str(BIN), *args], capture_output=True, text=True, errors="replace", timeout=15, check=False)
        out[key] = {
            "exit_code": cp.returncode,
            "stdout": (cp.stdout or "")[:12000],
            "stderr": (cp.stderr or "")[:4000],
        }
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
