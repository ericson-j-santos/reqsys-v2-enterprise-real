#!/usr/bin/env python3
"""Bootstrap governado do runner dedicado desktop-pc24x7-runtime via runner legado ReqSys."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

EXPECTED_HOST = "DESKTOP-PDQK954"
TARGET_REPOSITORY = "ericson-j-santos/desktop-pc24x7-runtime"
TARGET_SHA = "4f71186f3c7636ad80f8bd14c74e3fded28101ec"
TARGET_RUNNER = "DESKTOP-PDQK954-runtime"
TARGET_LABELS = ("self-hosted", "Windows", "X64", "pc24x7", "desktop-runtime")
CONFIRM = "BOOTSTRAP-DESKTOP-PC24X7-RUNTIME"
API_ROOT = "https://api.github.com"
Requester = Callable[[urllib.request.Request], dict[str, Any]]


class BridgeError(RuntimeError):
    pass


def request_json(request: urllib.request.Request) -> dict[str, Any]:
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise BridgeError("github_response_invalid")
    return payload


def api_request(token: str, path: str, *, method: str = "GET") -> urllib.request.Request:
    return urllib.request.Request(
        API_ROOT + path,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "ReqSys-Desktop-Runtime-Bootstrap/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def load_runtime_module(runtime_source: Path):
    script = runtime_source / "scripts" / "activate_desktop_runtime_runner.py"
    if not script.is_file():
        raise BridgeError("runtime_bootstrap_script_missing")
    spec = importlib.util.spec_from_file_location("desktop_runtime_activation", script)
    if spec is None or spec.loader is None:
        raise BridgeError("runtime_bootstrap_script_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_checkout(runtime_source: Path) -> None:
    cp = subprocess.run(
        ["git", "-C", str(runtime_source), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if cp.returncode != 0 or cp.stdout.strip().lower() != TARGET_SHA:
        raise BridgeError("runtime_checkout_sha_mismatch")


def snapshot(token: str, requester: Requester = request_json) -> dict[str, Any]:
    payload = requester(api_request(token, f"/repos/{TARGET_REPOSITORY}/actions/runners?per_page=100"))
    runners = payload.get("runners")
    if not isinstance(runners, list):
        raise BridgeError("runner_registry_invalid")
    matches = [
        item for item in runners
        if isinstance(item, dict)
        and str(item.get("name") or "").casefold() == TARGET_RUNNER.casefold()
    ]
    if not matches:
        return {"present": False, "status": "missing", "labels": [], "labels_ok": False}
    if len(matches) != 1:
        raise BridgeError("runner_registry_ambiguous")
    item = matches[0]
    labels = sorted(
        str(label.get("name") or "")
        for label in item.get("labels", [])
        if isinstance(label, dict) and str(label.get("name") or "")
    )
    required = {value.casefold() for value in TARGET_LABELS}
    observed = {value.casefold() for value in labels}
    return {
        "present": True,
        "status": str(item.get("status") or "unknown").casefold(),
        "labels": labels,
        "labels_ok": required.issubset(observed),
    }


def registration_token(token: str, requester: Requester = request_json) -> str:
    payload = requester(api_request(
        token,
        f"/repos/{TARGET_REPOSITORY}/actions/runners/registration-token",
        method="POST",
    ))
    value = str(payload.get("token") or "")
    if len(value) < 20:
        raise BridgeError("runner_registration_token_invalid")
    return value


def wait_online(token: str, requester: Requester = request_json, timeout_seconds: float = 45.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = snapshot(token, requester)
    while time.monotonic() < deadline:
        if last.get("present") and last.get("status") == "online" and last.get("labels_ok"):
            return last
        if last.get("present") and not last.get("labels_ok"):
            return last
        time.sleep(2)
        last = snapshot(token, requester)
    return last


def bootstrap(runtime_source: Path, token: str, requester: Requester = request_json) -> dict[str, Any]:
    verify_checkout(runtime_source)
    runtime = load_runtime_module(runtime_source)
    if runtime.EXPECTED_HOST != EXPECTED_HOST:
        raise BridgeError("runtime_host_contract_mismatch")
    if runtime.REPOSITORY != TARGET_REPOSITORY:
        raise BridgeError("runtime_repository_contract_mismatch")
    if runtime.RUNNER_NAME != TARGET_RUNNER:
        raise BridgeError("runtime_runner_contract_mismatch")

    host = runtime.validate_host()
    runner_home = runtime.default_runner_home().resolve()
    before = snapshot(token, requester)
    local_contract = runtime.runner_contract(runner_home) if runner_home.exists() else False

    registered_now = False
    if not local_contract:
        if before.get("present"):
            raise BridgeError("runner_registry_present_without_local_contract")
        runtime.ensure_runner_binaries(runner_home)
        ephemeral = registration_token(token, requester)
        try:
            runtime._register_runner_with_token(runner_home, ephemeral)
        finally:
            ephemeral = ""
        registered_now = True
    elif not before.get("present"):
        raise BridgeError("local_runner_registry_diverged")

    started_now = runtime.start_runner(runner_home)
    after = wait_online(token, requester)
    if not (
        after.get("present")
        and after.get("status") == "online"
        and after.get("labels_ok")
        and runtime.runner_running(runner_home)
    ):
        raise BridgeError("dedicated_runner_not_ready")

    return {
        "ok": True,
        "state": "dedicated_runner_ready",
        "host": host,
        "target_repository": TARGET_REPOSITORY,
        "target_sha": TARGET_SHA,
        "runner_name": TARGET_RUNNER,
        "runner_home": str(runner_home),
        "runner_registered_now": registered_now,
        "runner_started_now": bool(started_now),
        "registry_before": before,
        "registry_after": after,
        "legacy_reqsys_runner_preserved": True,
        "registration_token_consumed_in_memory": registered_now,
        "registration_token_persisted": False,
        "registration_token_logged": False,
        "production_touched": False,
        "reboot_performed": False,
    }


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--runtime-source", type=Path, required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    if args.confirm != CONFIRM:
        write_evidence(args.evidence_file, {"ok": False, "state": "confirmation_invalid"})
        return 2
    token = os.environ.get("GH_TOKEN") or ""
    if not token:
        write_evidence(args.evidence_file, {"ok": False, "state": "github_admin_token_missing"})
        return 2
    try:
        result = bootstrap(args.runtime_source.resolve(), token)
    except (BridgeError, urllib.error.URLError, urllib.error.HTTPError, OSError, subprocess.SubprocessError) as exc:
        result = {
            "ok": False,
            "state": str(exc)[:200] if isinstance(exc, BridgeError) else "bootstrap_failed",
            "error_type": type(exc).__name__,
            "target_repository": TARGET_REPOSITORY,
            "target_sha": TARGET_SHA,
            "legacy_reqsys_runner_preserved": True,
            "registration_token_persisted": False,
            "registration_token_logged": False,
            "production_touched": False,
            "reboot_performed": False,
        }
    write_evidence(args.evidence_file, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 4


if __name__ == "__main__":
    raise SystemExit(main())
