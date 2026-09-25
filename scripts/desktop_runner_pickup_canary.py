#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_HOST = "DESKTOP-PDQK954"
EXPECTED_RUNNER_NAME = "DESKTOP-PDQK954"
EXPECTED_RUNNER_OS = "Windows"
EXPECTED_RUNNER_ARCH = "X64"


class CanaryError(RuntimeError):
    pass


def validate_environment() -> dict:
    host = socket.gethostname()
    runner_name = str(os.environ.get("OBSERVED_RUNNER_NAME") or "").strip()
    runner_os = str(os.environ.get("OBSERVED_RUNNER_OS") or "").strip()
    runner_arch = str(os.environ.get("OBSERVED_RUNNER_ARCH") or "").strip()

    if host.casefold() != EXPECTED_HOST.casefold():
        raise CanaryError(f"host_mismatch:{host}")
    if runner_name.casefold() != EXPECTED_RUNNER_NAME.casefold():
        raise CanaryError(f"runner_name_mismatch:{runner_name}")
    if runner_os.casefold() != EXPECTED_RUNNER_OS.casefold():
        raise CanaryError(f"runner_os_mismatch:{runner_os}")
    if runner_arch.casefold() != EXPECTED_RUNNER_ARCH.casefold():
        raise CanaryError(f"runner_arch_mismatch:{runner_arch}")

    return {
        "ok": True,
        "host": host,
        "runner_name": runner_name,
        "runner_os": runner_os,
        "runner_arch": runner_arch,
        "physical_pickup_proven": True,
        "production_touched": False,
        "secrets_read": False,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = validate_environment()
        code = 0
    except Exception as exc:
        payload = {
            "ok": False,
            "host": socket.gethostname(),
            "runner_name": str(os.environ.get("OBSERVED_RUNNER_NAME") or ""),
            "runner_os": str(os.environ.get("OBSERVED_RUNNER_OS") or ""),
            "runner_arch": str(os.environ.get("OBSERVED_RUNNER_ARCH") or ""),
            "physical_pickup_proven": False,
            "error": str(exc)[:500],
            "error_type": type(exc).__name__,
            "production_touched": False,
            "secrets_read": False,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        code = 2
    args.evidence_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
