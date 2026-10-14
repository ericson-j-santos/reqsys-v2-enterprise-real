#!/usr/bin/env python3
"""Deterministic fake Command Gateway producer for wrapper contract tests."""
from __future__ import annotations
import argparse
import json
import sys

def emit(stream, value: dict[str, object]) -> None:
    stream.write(json.dumps(value, separators=(",", ":")))
    stream.flush()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("blocked", "malformed", "command-failed"), required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    if args.mode == "blocked":
        emit(sys.stderr, {"timestamp": "2026-10-14T03:08:55+00:00", "correlation_id": args.correlation_id, "result": "blocked", "gateway_exit_code": 20, "error": "PRIVATE_BLOCK_DETAIL"})
        return 20
    if args.mode == "malformed":
        sys.stderr.buffer.write(b"PRIVATE_INVALID_\xff")
        sys.stderr.buffer.flush()
        return 24
    emit(sys.stdout, {"result": "command_failed", "command_exit_code": 1, "gateway_exit_code": 1, "correlation_id": args.correlation_id, "session_id": args.session_id, "before": {"head": args.sha}, "after": {"head": args.sha}, "stdout": json.dumps({"ok": False, "category": "database_probe_failed"}, separators=(",", ":")), "stderr": "PRIVATE_COMMAND_STDERR"})
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
