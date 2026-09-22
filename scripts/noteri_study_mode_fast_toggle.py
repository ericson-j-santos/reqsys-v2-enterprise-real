#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EXPECTED_HOST = "Noteri"
AGENT = "http://127.0.0.1:8765"
PROFILE_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "ReqSys" / "TodoGlobal24x7" / "host-profile.json"


def http_json(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        AGENT + path,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Origin": "http://127.0.0.1:8083",
            "Cache-Control": "no-store",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return int(exc.code), json.loads(exc.read().decode("utf-8") or "{}")


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

    try:
        health_status, health = http_json("GET", "/health")
    except OSError:
        health_status, health = 0, {}

    if health_status != 200 or health.get("ok") is not True:
        control = Path(__file__).resolve().with_name("noteri_host_profile_agent_control.py")
        completed = subprocess.run(
            [sys.executable, str(control), "start", "--host", EXPECTED_HOST],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            return fail("profile_agent_start_failed")
        try:
            health_status, health = http_json("GET", "/health")
        except OSError:
            health_status, health = 0, {}
        if health_status != 200 or health.get("ok") is not True:
            return fail("profile_agent_unavailable")

    correlation_id = f"study-fast-toggle-{int(time.time())}"
    status, changed = http_json(
        "POST",
        "/v1/profile",
        {
            "host": EXPECTED_HOST,
            "profile": "ESTUDO",
            "correlation_id": correlation_id,
        },
    )
    if status != 200 or changed.get("ok") is not True:
        return fail("profile_change_failed")

    read_status, readback = http_json("GET", "/v1/profile")
    if read_status != 200 or readback.get("profile") != "ESTUDO":
        return fail("profile_readback_failed")
    if readback.get("accepts_new_development") is not False:
        return fail("acceptance_flag_mismatch")

    if not PROFILE_PATH.is_file():
        return fail("profile_file_missing")
    independent = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
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
        "agent_loopback_only": bool(health.get("loopback_only")),
        "correlation_id": correlation_id,
        "production_touched": False,
        "secrets_read": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
