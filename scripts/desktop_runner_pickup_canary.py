#!/usr/bin/env python3
"""Canário mínimo e sanitizado de pickup físico do runner DESKTOP-PDQK954."""
from __future__ import annotations

import argparse
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

TARGET_HOST = "DESKTOP-PDQK954"
CONFIRM = "PROVE-DESKTOP-GITHUB-RUNNER-PICKUP"


class CanaryError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_evidence(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def execute(*, confirm: str, evidence_file: Path, host: str | None = None, platform: str | None = None) -> dict:
    if confirm != CONFIRM:
        raise CanaryError("confirmation_invalid")
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_platform != "nt":
        raise CanaryError("windows_required")
    if actual_host.casefold() != TARGET_HOST.casefold():
        raise CanaryError(f"wrong_host:{actual_host}")
    runner_name = os.environ.get("RUNNER_NAME", "")
    if runner_name.casefold() != TARGET_HOST.casefold():
        raise CanaryError(f"runner_name_mismatch:{runner_name}")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    if repository != "ericson-j-santos/reqsys-v2-enterprise-real":
        raise CanaryError("repository_mismatch")
    if len(sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
        raise CanaryError("github_sha_invalid")

    evidence = {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "ok": True,
        "result": "DESKTOP_GITHUB_RUNNER_PICKUP_PROVEN",
        "host": actual_host,
        "runner_name": runner_name,
        "repository": repository,
        "sha": sha.lower(),
        "production_touched": False,
        "secrets_read": False,
    }
    write_evidence(evidence_file, evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("artifacts/desktop-runner-pickup/evidence.json"),
    )
    args = parser.parse_args()
    try:
        result = execute(confirm=args.confirm, evidence_file=args.evidence_file.resolve())
    except (CanaryError, OSError):
        blocked = {
            "schema_version": "1",
            "generated_at_utc": now_iso(),
            "ok": False,
            "result": "DESKTOP_GITHUB_RUNNER_PICKUP_NOT_PROVEN",
            "error": "desktop_runner_pickup_not_proven",
            "production_touched": False,
            "secrets_read": False,
        }
        write_evidence(args.evidence_file.resolve(), blocked)
        print(json.dumps(blocked, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
