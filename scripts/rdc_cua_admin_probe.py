#!/usr/bin/env python3
"""Probe de elevação lançado pelo CUA; não altera configuração do host."""
from __future__ import annotations
import argparse
import ctypes
import json
import os
import socket
from pathlib import Path

HOST = "DESKTOP-PDQK954"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    ns = parser.parse_args()
    payload = {
        "host": socket.gethostname(),
        "host_ok": socket.gethostname().casefold() == HOST.casefold(),
        "is_admin": bool(os.name == "nt" and ctypes.windll.shell32.IsUserAnAdmin()),
        "pid": os.getpid(),
        "ppid": os.getppid(),
    }
    ns.receipt.parent.mkdir(parents=True, exist_ok=True)
    ns.receipt.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
