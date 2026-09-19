#!/usr/bin/env python3
"""Governed remote control for the ReqSys Cofre DEV runtime.

The client never receives Docker/host credentials. It talks only to the
authenticated Cofre runtime-control API and proves a restart by observing a
new boot_id on the exact same runtime SHA.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CONFIRM = "RESTART-COFRE-DEV-RUNTIME"


class RemoteControlError(RuntimeError):
    pass


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class Client:
    def __init__(self, base_url: str, admin_jwt: str, correlation_id: str, timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.admin_jwt = admin_jwt.strip()
        self.correlation_id = correlation_id
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.admin_jwt}",
            "X-Correlation-ID": self.correlation_id,
            "User-Agent": "reqsys-cofre-remote-runtime-control/1.0",
        }
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        req = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout) as response:  # nosec B310
                status = int(response.status)
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            status = int(exc.code)
            raw = exc.read().decode("utf-8", errors="replace")
        except (URLError, TimeoutError) as exc:
            raise RemoteControlError(f"http_unavailable:{type(exc).__name__}") from exc
        if status not in expected:
            try:
                parsed = json.loads(raw) if raw else {}
                detail = str(parsed.get("detail") or parsed.get("message") or "unexpected_response")
            except json.JSONDecodeError:
                detail = "non_json_response"
            raise RemoteControlError(f"http_{status}:{detail[:200]}")
        parsed = json.loads(raw) if raw else {}
        data = parsed.get("data", parsed)
        if not isinstance(data, dict):
            raise RemoteControlError("invalid_response_envelope")
        return data


def inspect_runtime(client: Client, expected_sha: str) -> dict[str, Any]:
    data = client.request("GET", "/v1/cofre/runtime/control-status")
    if data.get("environment") != "dev":
        raise RemoteControlError("runtime_environment_not_dev")
    if data.get("runtime_target") != "pc24x7":
        raise RemoteControlError("runtime_target_mismatch")
    if data.get("self_restart_enabled") is not True:
        raise RemoteControlError("self_restart_not_enabled")
    if data.get("runtime_sha") != expected_sha:
        raise RemoteControlError("runtime_sha_mismatch")
    boot_id = str(data.get("boot_id") or "")
    if not boot_id:
        raise RemoteControlError("runtime_boot_id_missing")
    return {
        "ok": True,
        "environment": "dev",
        "runtime_target": "pc24x7",
        "runtime_sha": expected_sha,
        "boot_id": boot_id,
        "self_restart_enabled": True,
        "production_touched": False,
        "sensitive_values_exposed": False,
    }


def restart_runtime(client: Client, expected_sha: str) -> dict[str, Any]:
    before = inspect_runtime(client, expected_sha)
    result = client.request(
        "POST",
        "/v1/cofre/runtime/restart",
        payload={"expected_sha": expected_sha, "confirm": CONFIRM},
        expected=(202,),
    )
    if result.get("runtime_sha") != expected_sha:
        raise RemoteControlError("restart_response_sha_mismatch")
    if result.get("production_touched") is not False:
        raise RemoteControlError("restart_response_production_flag_invalid")
    if result.get("accepted") is not True and result.get("duplicate") is not True:
        raise RemoteControlError("restart_not_accepted")
    return {
        "ok": True,
        "environment": "dev",
        "runtime_target": "pc24x7",
        "runtime_sha": expected_sha,
        "before_boot_id": before["boot_id"],
        "accepted": bool(result.get("accepted")),
        "duplicate": bool(result.get("duplicate")),
        "restart_scheduled": bool(result.get("restart_scheduled")),
        "production_touched": False,
        "sensitive_values_exposed": False,
    }


def verify_restart(
    client: Client,
    expected_sha: str,
    before_boot_id: str,
    wait_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + wait_seconds
    last_error = "runtime_not_reachable"
    while time.monotonic() < deadline:
        try:
            current = inspect_runtime(client, expected_sha)
        except RemoteControlError as exc:
            last_error = str(exc)
            time.sleep(2)
            continue
        if current["boot_id"] != before_boot_id:
            return {
                "ok": True,
                "environment": "dev",
                "runtime_target": "pc24x7",
                "runtime_sha": expected_sha,
                "before_boot_id": before_boot_id,
                "after_boot_id": current["boot_id"],
                "boot_id_changed": True,
                "production_touched": False,
                "sensitive_values_exposed": False,
            }
        last_error = "boot_id_unchanged"
        time.sleep(2)
    raise RemoteControlError(f"restart_verification_timeout:{last_error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "restart", "verify"))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--admin-jwt", default=os.getenv("COFRE_ADMIN_JWT", ""))
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--wait-seconds", type=int, default=180)
    parser.add_argument("--restart-evidence-file", type=Path)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    if not args.admin_jwt.strip():
        parser.error("--admin-jwt ou COFRE_ADMIN_JWT é obrigatório")
    if len(args.expected_sha) != 40 or any(ch not in "0123456789abcdef" for ch in args.expected_sha.lower()):
        parser.error("--expected-sha deve ser SHA completo")
    if args.action == "verify" and args.restart_evidence_file is None:
        parser.error("--restart-evidence-file é obrigatório para verify")
    return args


def main() -> int:
    args = parse_args()
    client = Client(args.base_url, args.admin_jwt, args.correlation_id, args.timeout)
    try:
        if args.action == "inspect":
            result = inspect_runtime(client, args.expected_sha.lower())
        elif args.action == "restart":
            result = restart_runtime(client, args.expected_sha.lower())
        else:
            restart_evidence = json.loads(args.restart_evidence_file.read_text(encoding="utf-8"))
            before_boot_id = str(restart_evidence.get("before_boot_id") or "")
            if not before_boot_id:
                raise RemoteControlError("restart_evidence_missing_before_boot_id")
            result = verify_restart(
                client,
                args.expected_sha.lower(),
                before_boot_id,
                args.wait_seconds,
            )
        _write_json(args.evidence_file, result)
        print(json.dumps({"ok": True, "action": args.action, "evidence_file": str(args.evidence_file)}))
        return 0
    except Exception as exc:
        failure = {
            "ok": False,
            "action": args.action,
            "error": str(exc),
            "production_touched": False,
            "sensitive_values_exposed": False,
        }
        _write_json(args.evidence_file, failure)
        print(json.dumps(failure), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
