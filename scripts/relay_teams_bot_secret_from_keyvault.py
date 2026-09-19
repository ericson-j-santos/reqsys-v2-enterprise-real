#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class SendError(RuntimeError):
    pass


def _az() -> str:
    for candidate in ("az", "az.cmd", "az.exe", "az.bat"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise SendError("azure_cli_missing")


def _read_secret(vault_name: str, secret_name: str) -> tuple[str, str]:
    result = subprocess.run(
        [
            _az(), "keyvault", "secret", "show",
            "--vault-name", vault_name,
            "--name", secret_name,
            "--query", '{value:value,app_id:tags."app-id",enabled:attributes.enabled}',
            "--output", "json",
            "--only-show-errors",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=90,
        shell=False,
    )
    if result.returncode != 0:
        raise SendError("keyvault_secret_read_failed")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise SendError("keyvault_payload_invalid") from exc
    if not isinstance(payload, dict) or payload.get("enabled") is False:
        raise SendError("keyvault_secret_unavailable")
    app_id = str(payload.get("app_id") or "").strip()
    secret_value = str(payload.get("value") or "")
    if not app_id or not secret_value:
        raise SendError("keyvault_secret_incomplete")
    return app_id, secret_value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-name", required=True)
    parser.add_argument("--secret-name", required=True)
    parser.add_argument("--expected-app-id", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--relay-url", required=True)
    parser.add_argument("--public-key-b64", required=True)
    args = parser.parse_args()

    app_id, secret_value = _read_secret(args.vault_name, args.secret_name)
    if app_id != args.expected_app_id:
        raise SendError("app_id_tag_mismatch")

    public_key = serialization.load_der_public_key(base64.b64decode(args.public_key_b64, validate=True))
    ciphertext = public_key.encrypt(
        secret_value.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    secret_value = ""
    data = json.dumps({
        "app_id": args.expected_app_id,
        "tenant_id": args.tenant_id,
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
    }).encode("utf-8")
    request = urllib.request.Request(
        args.relay_url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            payload = json.loads(response.read().decode("utf-8"))
            status = int(response.status)
    except Exception as exc:
        raise SendError(f"relay_request_failed:{type(exc).__name__}") from exc
    safe = {
        "status": "sent" if status == 200 and payload.get("status") == "passed" else "blocked",
        "receiver_status": payload.get("status"),
        "credential_validated": payload.get("credential_validated") is True,
        "runtime_sha": payload.get("runtime_sha"),
        "secret_value_exposed": False,
        "production_touched": False,
    }
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0 if safe["status"] == "sent" else 4


if __name__ == "__main__":
    raise SystemExit(main())
