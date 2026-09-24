from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

VALID_PROFILES = {"NORMAL", "ESTUDO"}


def default_profile_path() -> Path | None:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    return Path(base) / "ReqSys" / "TodoGlobal24x7" / "host-profile.json"


def resolve_profile(path: Path | None) -> str:
    if path is None or not path.exists():
        return "NORMAL"
    payload = json.loads(path.read_text(encoding="utf-8"))
    profile = payload.get("profile")
    if profile not in VALID_PROFILES:
        raise ValueError("invalid host profile")
    return profile


def post_json(url: str, payload: dict) -> tuple[int, dict]:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    request = Request(
        url,
        data=raw,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"heartbeat endpoint unavailable: {type(exc.reason).__name__}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument(
        "--roles",
        nargs="+",
        default=["builder", "ci-remediator", "e2e-validator"],
    )
    parser.add_argument("--controller-version", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--dispatch-priority", type=int, default=100)
    parser.add_argument("--ttl-seconds", type=int, default=120)
    parser.add_argument("--transport-broadcast-v1", action="store_true")
    parser.add_argument("--auth-valid", action="store_true")
    parser.add_argument("--controller-online", action="store_true")
    parser.add_argument("--profile-file")
    args = parser.parse_args()

    profile_path = Path(args.profile_file) if args.profile_file else default_profile_path()
    profile = resolve_profile(profile_path)
    device_name = socket.gethostname()

    payload = {
        "worker_id": args.worker_id,
        "device_name": device_name,
        "roles": args.roles,
        "capabilities": {
            "dispatch_priority": args.dispatch_priority,
            "transport_broadcast_v1": args.transport_broadcast_v1,
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "source": "host-self-report",
        },
        "profile": profile,
        "controller_online": args.controller_online,
        "auth_valid": args.auth_valid,
        "controller_version": args.controller_version,
        "correlation_id": args.correlation_id,
        "heartbeat_ttl_seconds": args.ttl_seconds,
    }
    endpoint = args.endpoint.rstrip("/") + "/v1/workers/heartbeat"
    status, response = post_json(endpoint, payload)
    if status != 200:
        print(json.dumps({"status": status, "response": response}, sort_keys=True))
        raise SystemExit(2)
    worker = response["worker"]
    if worker["worker_id"] != args.worker_id or worker["profile"] != profile:
        raise SystemExit("heartbeat readback mismatch")
    print(
        json.dumps(
            {
                "ok": True,
                "worker_id": worker["worker_id"],
                "device_name": worker["device_name"],
                "profile": worker["profile"],
                "eligible": worker["eligible"],
                "fresh": worker["fresh"],
                "correlation_id": args.correlation_id,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
