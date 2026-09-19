#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

MAX_BODY = 16384


class RelayError(RuntimeError):
    pass


def _run(args: list[str], *, cwd: Path, env: dict[str, str], timeout: int, sensitive: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        if sensitive:
            raise RelayError(f"sensitive_command_failed:{Path(args[0]).name}:exit_{result.returncode}")
        detail = (result.stderr or result.stdout or "sem detalhe").strip().replace("\n", " ")
        raise RelayError(f"command_failed:{Path(args[0]).name}:exit_{result.returncode}:{detail[:500]}")
    return result


def _json_from_stdout(result: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    for raw in reversed([line.strip() for line in (result.stdout or "").splitlines() if line.strip()]):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise RelayError(f"{label}_json_missing")


def _validate_bot_credential(tenant_id: str, app_id: str, secret: str) -> bool:
    body = urllib.parse.urlencode({
        "client_id": app_id,
        "client_secret": secret,
        "grant_type": "client_credentials",
        "scope": "https://api.botframework.com/.default",
    }).encode("utf-8")
    request = urllib.request.Request(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return False
    token = str(payload.get("access_token") or "") if isinstance(payload, dict) else ""
    return bool(token)


def execute_runtime(args: argparse.Namespace, bot_secret: str) -> dict[str, Any]:
    runtime = args.runtime_repo_root.resolve()
    if not runtime.is_dir():
        raise RelayError("runtime_repo_missing")

    env = os.environ.copy()
    env["TEAMS_BOT_APP_ID"] = args.expected_app_id
    env["TEAMS_BOT_APP_TENANT_ID"] = args.expected_tenant_id
    env["TEAMS_BOT_SECRET"] = bot_secret

    recreate = _run(
        [
            sys.executable,
            str(runtime / "scripts" / "recreate_cofre_dev_pc24x7.py"),
            "--repo-root", str(runtime),
            "--expected-sha", args.expected_runtime_sha,
            "--admin-override", str(args.admin_override.resolve()),
            "--teams-override", str(args.teams_override.resolve()),
            "--health-timeout", "240",
        ],
        cwd=runtime,
        env=env,
        timeout=720,
        sensitive=True,
    )
    recreate_evidence = _json_from_stdout(recreate, "recreate")

    env["TEAMS_BOT_SECRET"] = ""
    bot_secret = ""

    e2e = _run(
        [
            sys.executable,
            str(runtime / "scripts" / "pc24x7_teams_ephemeral_e2e.py"),
            "--api-base", "http://127.0.0.1:8210",
            "--correlation-id", args.correlation_id,
            "--evidence-path", str(args.e2e_detail.resolve()),
        ],
        cwd=runtime,
        env=env,
        timeout=600,
    )
    e2e_evidence = _json_from_stdout(e2e, "e2e")
    delivered = any(
        isinstance(item, dict)
        and item.get("teams_delivered") is True
        and item.get("teams_channel") == "bot"
        for item in e2e_evidence.get("delivery_attempts", [])
    )
    passed = bool(
        recreate_evidence.get("ok") is True
        and e2e_evidence.get("status") == "done"
        and e2e_evidence.get("token_revoked") is True
        and e2e_evidence.get("turn_idempotency_proven") is True
        and delivered
    )
    evidence = {
        "status": "passed" if passed else "blocked",
        "environment": "dev",
        "runtime_sha": args.expected_runtime_sha,
        "correlation_id": args.correlation_id,
        "credential_source": "azure_key_vault_existing_via_oidc_encrypted_relay",
        "credential_validated": True,
        "credential_rotated": False,
        "secret_value_exposed": False,
        "production_touched": False,
        "recreate": recreate_evidence,
        "e2e": e2e_evidence,
    }
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=8233)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--expected-app-id", required=True)
    parser.add_argument("--expected-tenant-id", required=True)
    parser.add_argument("--runtime-repo-root", type=Path, required=True)
    parser.add_argument("--expected-runtime-sha", required=True)
    parser.add_argument("--admin-override", type=Path, required=True)
    parser.add_argument("--teams-override", type=Path, required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--e2e-detail", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_der = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    relay_path = "/relay/" + secrets.token_urlsafe(24)
    state: dict[str, Any] = {"done": False, "accepted": False, "result": None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            return

        def do_POST(self) -> None:
            if self.path != relay_path or state["done"]:
                self.send_response(404)
                self.end_headers()
                return
            try:
                length = int(self.headers.get("Content-Length") or "0")
                if length <= 0 or length > MAX_BODY:
                    raise RelayError("invalid_body_length")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise RelayError("invalid_payload")
                if str(payload.get("app_id") or "") != args.expected_app_id:
                    raise RelayError("app_id_mismatch")
                if str(payload.get("tenant_id") or "") != args.expected_tenant_id:
                    raise RelayError("tenant_id_mismatch")
                ciphertext = base64.b64decode(str(payload.get("ciphertext_b64") or ""), validate=True)
                secret_value = private_key.decrypt(
                    ciphertext,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None,
                    ),
                ).decode("utf-8")
                if not _validate_bot_credential(args.expected_tenant_id, args.expected_app_id, secret_value):
                    raise RelayError("bot_credential_validation_failed")
                result = execute_runtime(args, secret_value)
                secret_value = ""
                state["accepted"] = True
                state["result"] = result
                state["done"] = True
                response = {
                    "status": result.get("status"),
                    "credential_validated": True,
                    "runtime_sha": result.get("runtime_sha"),
                    "secret_value_exposed": False,
                    "production_touched": False,
                }
                data = json.dumps(response).encode("utf-8")
                self.send_response(200 if result.get("status") == "passed" else 409)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as exc:
                response = {
                    "status": "rejected",
                    "reason": type(exc).__name__,
                    "secret_value_exposed": False,
                    "production_touched": False,
                }
                data = json.dumps(response).encode("utf-8")
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

    server = ThreadingHTTPServer((args.listen_host, args.listen_port), Handler)
    server.timeout = 2
    print(json.dumps({
        "status": "ready",
        "listen_port": args.listen_port,
        "relay_path": relay_path,
        "public_key_b64": base64.b64encode(public_der).decode("ascii"),
        "expected_app_id": args.expected_app_id,
        "expected_tenant_id": args.expected_tenant_id,
        "secret_value_exposed": False,
        "production_touched": False,
    }, sort_keys=True), flush=True)

    deadline = time.monotonic() + args.timeout_seconds
    while time.monotonic() < deadline and not state["done"]:
        server.handle_request()
    server.server_close()

    if not state["done"]:
        print(json.dumps({
            "status": "timeout",
            "secret_value_exposed": False,
            "production_touched": False,
        }, sort_keys=True), flush=True)
        return 4

    print(json.dumps({
        "status": state["result"].get("status") if isinstance(state["result"], dict) else "blocked",
        "credential_validated": state["accepted"],
        "secret_value_exposed": False,
        "production_touched": False,
    }, sort_keys=True), flush=True)
    return 0 if isinstance(state["result"], dict) and state["result"].get("status") == "passed" else 4


if __name__ == "__main__":
    raise SystemExit(main())
