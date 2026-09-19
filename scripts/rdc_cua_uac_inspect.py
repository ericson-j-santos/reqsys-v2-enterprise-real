#!/usr/bin/env python3
"""Busca read-only por UAC na superfície visível ao CUA."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

BIN = Path(r"C:\Users\Windows\AppData\Local\Programs\Cua\cua-driver\bin\cua-driver.exe")
SESSION = "rdc-uac-watchdog"
KEYWORDS = (
    "consent",
    "user account control",
    "controle de conta",
    "deseja permitir",
    "want to allow",
    "sim",
    "yes",
    "administrador",
    "administrator",
)


def call(tool: str, payload: dict) -> dict:
    cp = subprocess.run(
        [str(BIN), "call", tool, json.dumps(payload, separators=(",", ":"))],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
        check=False,
    )
    return {"exit_code": cp.returncode, "stdout": cp.stdout or "", "stderr": cp.stderr or ""}


def snippets(text: str) -> list[str]:
    lowered = text.casefold()
    out: list[str] = []
    for keyword in KEYWORDS:
        start = 0
        needle = keyword.casefold()
        while True:
            idx = lowered.find(needle, start)
            if idx < 0:
                break
            lo = max(0, idx - 240)
            hi = min(len(text), idx + len(keyword) + 420)
            piece = text[lo:hi].replace("\r", " ").replace("\n", " ")
            if piece not in out:
                out.append(piece)
            start = idx + len(needle)
            if len(out) >= 30:
                return out
    return out


def main() -> int:
    windows = call("list_windows", {"session": SESSION})
    tree = call("get_accessibility_tree", {"session": SESSION})
    result = {
        "windows_exit_code": windows["exit_code"],
        "tree_exit_code": tree["exit_code"],
        "matches_windows": snippets(windows["stdout"]),
        "matches_tree": snippets(tree["stdout"]),
        "windows_stderr": windows["stderr"][:1000],
        "tree_stderr": tree["stderr"][:1000],
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
