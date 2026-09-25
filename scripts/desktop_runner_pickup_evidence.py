#!/usr/bin/env python3
"""Prova independente de pickup do GitHub Actions no Desktop PC24x7."""

from __future__ import annotations

import argparse
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

TARGET_HOST = "DESKTOP-PDQK954"
CONFIRM = "PROVE-DESKTOP-GITHUB-RUNNER-PICKUP"


class PickupError(RuntimeError):
    pass


def prove(confirm: str, correlation_id: str, *, host: str | None = None, platform: str | None = None) -> dict:
    if confirm != CONFIRM:
        raise PickupError("confirmation_invalid")
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_platform != "nt":
        raise PickupError("windows_required")
    if actual_host.casefold() != TARGET_HOST.casefold():
        raise PickupError(f"unexpected_runner_host:{actual_host}")
    correlation = correlation_id.strip()
    if not 8 <= len(correlation) <= 160:
        raise PickupError("correlation_id_invalid")
    return {
        "schema_version": "1",
        "ok": True,
        "result": "DESKTOP_GITHUB_RUNNER_PICKUP_PROVEN",
        "target_host": TARGET_HOST,
        "correlation_id": correlation,
        "github_runner_pickup_proven": True,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "secrets_read": False,
        "production_touched": False,
        "reboot_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = prove(args.confirm, args.correlation_id)
        code = 0
    except PickupError as exc:
        payload = {
            "schema_version": "1",
            "ok": False,
            "result": "DESKTOP_GITHUB_RUNNER_PICKUP_NOT_PROVEN",
            "error": str(exc)[:300],
            "correlation_id": args.correlation_id,
            "secrets_read": False,
            "production_touched": False,
            "reboot_performed": False,
        }
        code = 2
    path = args.evidence_file.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
