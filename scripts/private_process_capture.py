#!/usr/bin/env python3
"""Capture a child process without exposing its stdout or stderr."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdout-path", required=True, type=Path)
    parser.add_argument("--stderr-path", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a command is required after --")
    try:
        completed = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        args.stdout_path.write_bytes(completed.stdout)
        args.stderr_path.write_bytes(completed.stderr)
        return completed.returncode
    except Exception:
        # Fail closed without printing paths, arguments, stderr, or exception details.
        try:
            args.stdout_path.write_bytes(b"")
            args.stderr_path.write_bytes(b"")
        except OSError:
            pass
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
