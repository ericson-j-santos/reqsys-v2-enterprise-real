"""Read-only Noteri worker heartbeat proof through the governed Command Gateway."""
from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "http://DESKTOP-PDQK954:8787/v1/workers"
EXPECTED_HOST = "Noteri"
EXPECTED_ID = "noteri"
REQUIRED_CAPABILITY = "host.profile.set.v1"
SHA_RE = re.compile(r"^[a-fA-F0-9]{40}$")


class ProbeBlocked(RuntimeError):
    """A mandatory readback precondition was not proven."""


def source_sha(root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
        text=True, timeout=10, check=False,
    )
    if proc.returncode != 0 or not SHA_RE.fullmatch(proc.stdout.strip()):
        raise ProbeBlocked("source_sha_unavailable")
    return proc.stdout.strip().lower()


def fetch_workers() -> dict[str, Any]:
    request = Request(ENDPOINT, headers={"Accept": "application/json", "Cache-Control": "no-store"})
    try:
        with urlopen(request, timeout=6) as response:
            if response.status != 200:
                raise ProbeBlocked("worker_registry_http_error")
            payload = json.load(response)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        raise ProbeBlocked(f"worker_registry_unavailable:{type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise ProbeBlocked("worker_registry_payload_invalid")
    return payload


def snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    workers = payload.get("workers")
    if not isinstance(workers, list):
        raise ProbeBlocked("worker_list_invalid")
    matches = [w for w in workers if isinstance(w, dict)
               and str(w.get("worker_id") or "").casefold() == EXPECTED_ID
               and str(w.get("device_name") or "").casefold() == EXPECTED_HOST.casefold()]
    if len(matches) != 1:
        raise ProbeBlocked("noteri_worker_ambiguous_or_missing")
    item = matches[0]
    caps = item.get("capabilities")
    types = caps.get("safe_task_types") if isinstance(caps, dict) else None
    if not isinstance(types, list) or REQUIRED_CAPABILITY not in types:
        raise ProbeBlocked("noteri_profile_capability_missing")
    if item.get("fresh") is not True or item.get("controller_online") is not True or item.get("auth_valid") is not True:
        raise ProbeBlocked("noteri_worker_not_operational")
    profile = item.get("profile")
    if profile not in {"NORMAL", "ESTUDO"}:
        raise ProbeBlocked("noteri_profile_invalid")
    raw = item.get("last_heartbeat")
    try:
        stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProbeBlocked("noteri_heartbeat_timestamp_invalid") from exc
    if stamp.tzinfo is None:
        raise ProbeBlocked("noteri_heartbeat_timezone_missing")
    return {"profile": profile, "last_heartbeat": stamp, "worker_id": EXPECTED_ID}


def check(
    *, expected_sha: str, correlation_id: str, interval_seconds: float = 25.0,
    host: str | None = None, root: Path | None = None,
    fetch: Callable[[], dict[str, Any]] = fetch_workers,
    sleep: Callable[[float], None] = time.sleep,
    get_sha: Callable[[Path], str] = source_sha,
) -> dict[str, Any]:
    if (host or socket.gethostname()).casefold() != EXPECTED_HOST.casefold():
        raise ProbeBlocked("host_mismatch")
    if not SHA_RE.fullmatch(expected_sha):
        raise ProbeBlocked("expected_sha_invalid")
    if not 8 <= len(correlation_id) <= 128:
        raise ProbeBlocked("correlation_id_invalid")
    if not 20 <= interval_seconds <= 90:
        raise ProbeBlocked("interval_invalid")
    observed_sha = get_sha(root or Path(__file__).resolve().parents[1]).lower()
    if observed_sha != expected_sha.lower():
        raise ProbeBlocked("source_sha_mismatch")
    first = snapshot(fetch())
    sleep(interval_seconds)
    second = snapshot(fetch())
    if second["last_heartbeat"] <= first["last_heartbeat"]:
        raise ProbeBlocked("noteri_heartbeat_not_advanced")
    return {
        "ok": True,
        "host": EXPECTED_HOST,
        "environment": "dev",
        "worker_id": EXPECTED_ID,
        "profile": second["profile"],
        "heartbeat_advanced": True,
        "first_heartbeat": first["last_heartbeat"].isoformat(),
        "second_heartbeat": second["last_heartbeat"].isoformat(),
        "expected_sha": expected_sha.lower(),
        "observed_sha": observed_sha,
        "correlation_id": correlation_id,
        "read_only": True,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args()
    try:
        result = check(expected_sha=args.expected_sha, correlation_id=args.correlation_id)
    except ProbeBlocked as exc:
        print(json.dumps({"ok": False, "reason": str(exc), "correlation_id": args.correlation_id}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
