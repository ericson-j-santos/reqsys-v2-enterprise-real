#!/usr/bin/env python3
"""Extrai do manifest a sintaxe do subcommand call do CUA."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

BIN = Path(r"C:\Users\Windows\AppData\Local\Programs\Cua\cua-driver\bin\cua-driver.exe")


def collect_call_nodes(value):
    found = []
    if isinstance(value, dict):
        if value.get("name") == "call":
            found.append(value)
        if "call" in value:
            found.append({"call": value["call"]})
        for child in value.values():
            found.extend(collect_call_nodes(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(collect_call_nodes(child))
    return found


def main() -> int:
    cp = subprocess.run([str(BIN), "manifest"], capture_output=True, text=True, errors="replace", timeout=15, check=False)
    result = {"exit_code": cp.returncode, "stderr": (cp.stderr or "")[:2000]}
    if cp.returncode == 0:
        try:
            payload = json.loads(cp.stdout)
            result["call_nodes"] = collect_call_nodes(payload)[:10]
            result["top_keys"] = list(payload)[:30] if isinstance(payload, dict) else []
        except json.JSONDecodeError:
            result["manifest_prefix"] = (cp.stdout or "")[:8000]
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
