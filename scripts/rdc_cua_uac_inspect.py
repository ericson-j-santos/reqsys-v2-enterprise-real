#!/usr/bin/env python3
"""Inspeção read-only do desktop via CUA durante UAC."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

BIN = Path(r"C:\Users\Windows\AppData\Local\Programs\Cua\cua-driver\bin\cua-driver.exe")
SESSION = "rdc-uac-watchdog"
SHOT = Path(r"C:\dev\chatgpt-workers\artifacts\rdc-uac-desktop.png")


def call(tool: str, payload: dict) -> dict:
    cp = subprocess.run(
        [str(BIN), "call", tool, json.dumps(payload, separators=(",", ":"))],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
        check=False,
    )
    return {
        "tool": tool,
        "exit_code": cp.returncode,
        "stdout": (cp.stdout or "")[:24000],
        "stderr": (cp.stderr or "")[:4000],
    }


def main() -> int:
    SHOT.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "desktop": call("get_desktop_state", {"session": SESSION, "screenshot_out_file": str(SHOT)}),
        "windows": call("list_windows", {"session": SESSION}),
        "tree": call("get_accessibility_tree", {"session": SESSION}),
        "screenshot_path": str(SHOT),
        "screenshot_exists": SHOT.is_file(),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
