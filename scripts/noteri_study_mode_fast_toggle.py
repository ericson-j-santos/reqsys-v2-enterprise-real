#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path

from noteri_host_profile_agent import set_profile

EXPECTED_HOST = "Noteri"
PROFILE_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "ReqSys" / "TodoGlobal24x7" / "host-profile.json"


def fail(code: str) -> int:
    print(json.dumps({
        "ok": False,
        "error": code,
        "host": socket.gethostname(),
        "production_touched": False,
        "secrets_read": False,
    }, sort_keys=True))
    return 2


def main() -> int:
    if os.name != "nt":
        return fail("windows_required")
    if socket.gethostname().casefold() != EXPECTED_HOST.casefold():
        return fail("host_not_allowed")

    correlation_id = f"study-fast-toggle-{int(time.time())}"
    try:
        changed = set_profile(
            PROFILE_PATH,
            expected_host=EXPECTED_HOST,
            profile="ESTUDO",
            correlation_id=correlation_id,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError):
        return fail("profile_change_failed")

    if not PROFILE_PATH.is_file():
        return fail("profile_file_missing")
    independent = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    if independent.get("host", "").casefold() != EXPECTED_HOST.casefold():
        return fail("independent_host_mismatch")
    if independent.get("profile") != "ESTUDO":
        return fail("independent_file_readback_failed")
    if independent.get("accepts_new_development") is not False:
        return fail("independent_acceptance_flag_mismatch")

    print(json.dumps({
        "ok": True,
        "host": EXPECTED_HOST,
        "profile": "ESTUDO",
        "changed": bool(changed.get("changed")),
        "accepts_new_development": False,
        "independent_readback": True,
        "source": "canonical_host_profile_file",
        "correlation_id": correlation_id,
        "production_touched": False,
        "secrets_read": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
