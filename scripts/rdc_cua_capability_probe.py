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
    for args, key in [
        (["call", "--help"], "call_help"),
        (["describe", "get_desktop_state"], "describe_desktop"),
        (["describe", "click"], "describe_click"),
    ]:
        cp = subprocess.run([str(BIN), *args], capture_output=True, text=True, errors="replace", timeout=15, check=False)
        out[key] = {
            "exit_code": cp.returncode,
            "stdout": (cp.stdout or "")[:8000],
            "stderr": (cp.stderr or "")[:2000],
        }
    print(json.dumps(out, sort_keys=True))
        return 0
    out["sha256"] = hashlib.sha256(BIN.read_bytes()).hexdigest()
    for args, key in [
        (["call", "--help"], "call_help"),
        (["describe", "get_desktop_state"], "describe_desktop"),
        (["describe", "get_accessibility_tree"], "describe_tree"),
        (["describe", "click"], "describe_click"),
        (["describe", "list_windows"], "describe_windows"),
    ]:
        cp = subprocess.run([str(BIN), *args], capture_output=True, text=True, errors="replace", timeout=15, check=False)
        out[key] = {
            "exit_code": cp.returncode,
            "stdout": (cp.stdout or "")[:12000],
            "stderr": (cp.stderr or "")[:4000],
        }
    print(json.dumps(out, sort_keys=True))
        return 0
    out["sha256"] = hashlib.sha256(BIN.read_bytes()).hexdigest()
    for args, key in [
        (["status", "--json"], "status"),
        (["list-tools"], "list_tools"),
        (["call", "--help"], "call_help"),
        (["describe", "--help"], "describe_help"),
    ]:
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
