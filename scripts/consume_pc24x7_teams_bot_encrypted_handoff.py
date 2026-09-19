#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

RUNTIME_SHA = "0649ef8ee9b533b44ee05f15c9158856fefd8ad7"
HANDOFF_SHA = "b733f245b03679e44deb554748ffb916d7789001"
ALGORITHM = "RSA-OAEP-SHA256"


class ConsumeError(RuntimeError):
    pass


def _run(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 120,
    sensitive: bool = False,
    allow_nonzero: bool = False,
) -> subprocess.CompletedProcess[str]:
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
    if result.returncode != 0 and not allow_nonzero:
        if sensitive:
            raise ConsumeError(f"sensitive_command_failed:{Path(args[0]).name}:exit_{result.returncode}")
        detail = (result.stderr or result.stdout or "sem detalhe").strip().replace("\n", " ")
        raise ConsumeError(f"command_failed:{Path(args[0]).name}:exit_{result.returncode}:{detail[:400]}")
    return result


def _json_from_stdout(result: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    for raw in reversed([line.strip() for line in (result.stdout or "").splitlines() if line.strip()]):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ConsumeError(f"{label}_json_missing")


def _git_head(repo: Path) -> str:
    return _run(["git", "rev-parse", "HEAD"], cwd=repo, timeout=30).stdout.strip()


def _load_envelope(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConsumeError("envelope_invalid") from exc
    if not isinstance(payload, dict):
        raise ConsumeError("envelope_invalid")
    if payload.get("status") != "encrypted" or payload.get("environment") != "dev":
        raise ConsumeError("envelope_scope_invalid")
    if payload.get("algorithm") != ALGORITHM:
        raise ConsumeError("envelope_algorithm_invalid")
    if payload.get("handoff_sha") != HANDOFF_SHA:
        raise ConsumeError("envelope_handoff_sha_mismatch")
    if payload.get("credential_rotated") is not False:
        raise ConsumeError("rotated_credential_not_authorized")
    if payload.get("secret_value_exposed") is not False or payload.get("production_touched") is not False:
        raise ConsumeError("envelope_safety_contract_invalid")
    app_id = str(payload.get("app_id") or "")
    tenant_id = str(payload.get("tenant_id") or "")
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", app_id) or not re.fullmatch(r"[0-9a-fA-F-]{36}", tenant_id):
        raise ConsumeError("bot_identity_invalid")
    if not str(payload.get("ciphertext_b64") or ""):
        raise ConsumeError("ciphertext_missing")
    return payload


def _decrypt_secret(private_key_path: Path, ciphertext_b64: str) -> str:
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError as exc:
        raise ConsumeError("python_cryptography_missing") from exc
    try:
        private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
        ciphertext = base64.b64decode(ciphertext_b64, validate=True)
        clear = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        secret = clear.decode("utf-8")
    except Exception as exc:
        raise ConsumeError("envelope_decrypt_failed") from exc
    if len(secret) < 16:
        raise ConsumeError("decrypted_secret_invalid")
    return secret


def _delivery_proven(e2e: dict[str, Any]) -> bool:
    attempts = e2e.get("delivery_attempts") or []
    return any(
        isinstance(item, dict)
        and item.get("teams_delivered") is True
        and item.get("teams_channel") == "bot"
        for item in attempts
    )


def execute(args: argparse.Namespace) -> dict[str, Any]:
    runtime_root = args.runtime_repo_root.resolve()
    if _git_head(runtime_root) != RUNTIME_SHA:
        raise ConsumeError("runtime_sha_mismatch")
    if not args.private_key.is_file():
        raise ConsumeError("private_key_missing")
    if not args.admin_override.is_file() or not args.teams_override.is_file():
        raise ConsumeError("runtime_override_missing")

    envelope = _load_envelope(args.envelope.resolve())
    secret = _decrypt_secret(args.private_key.resolve(), str(envelope["ciphertext_b64"]))

    child_env = os.environ.copy()
    child_env["TEAMS_BOT_APP_ID"] = str(envelope["app_id"])
    child_env["TEAMS_BOT_APP_TENANT_ID"] = str(envelope["tenant_id"])
    child_env["TEAMS_BOT_SECRET"] = secret

    recreate = _run(
        [
            sys.executable,
            str(runtime_root / "scripts" / "recreate_cofre_dev_pc24x7.py"),
            "--repo-root", str(runtime_root),
            "--expected-sha", RUNTIME_SHA,
            "--admin-override", str(args.admin_override.resolve()),
            "--teams-override", str(args.teams_override.resolve()),
            "--health-timeout", "240",
        ],
        cwd=runtime_root,
        env=child_env,
        timeout=720,
        sensitive=True,
    )
    recreate_evidence = _json_from_stdout(recreate, "recreate")
    if recreate_evidence.get("ok") is not True or recreate_evidence.get("runtime_sha") != RUNTIME_SHA:
        raise ConsumeError("runtime_recreate_not_proven")

    child_env.pop("TEAMS_BOT_SECRET", None)
    secret = ""
    try:
        args.private_key.unlink()
    except OSError as exc:
        raise ConsumeError("private_key_cleanup_failed") from exc

    e2e_path = args.evidence_file.with_name("teams-bot-e2e-detail.json")
    e2e_result = _run(
        [
            sys.executable,
            str(runtime_root / "scripts" / "pc24x7_teams_ephemeral_e2e.py"),
            "--api-base", "http://127.0.0.1:8210",
            "--correlation-id", args.correlation_id,
            "--evidence-path", str(e2e_path.resolve()),
        ],
        cwd=runtime_root,
        env=child_env,
        timeout=600,
        allow_nonzero=True,
    )
    e2e = _json_from_stdout(e2e_result, "e2e")
    readiness = e2e.get("readiness") if isinstance(e2e.get("readiness"), dict) else {}
    passed = bool(
        e2e.get("status") == "done"
        and e2e.get("token_revoked") is True
        and readiness.get("ready") is True
        and e2e.get("turn_idempotency_proven") is True
        and _delivery_proven(e2e)
    )

    evidence = {
        "schema_version": "1.0.0",
        "status": "passed" if passed else "blocked",
        "environment": "dev",
        "runtime_sha": RUNTIME_SHA,
        "handoff_sha": HANDOFF_SHA,
        "correlation_id": args.correlation_id,
        "credential_source": "azure_key_vault_existing_via_rsa_oaep_handoff",
        "credential_rotated": False,
        "private_key_deleted_after_recreate": True,
        "secret_value_exposed": False,
        "production_touched": False,
        "recreate": recreate_evidence,
        "e2e": e2e,
    }
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-repo-root", type=Path, required=True)
    parser.add_argument("--envelope", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--admin-override", type=Path, required=True)
    parser.add_argument("--teams-override", type=Path, required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        evidence = execute(args)
    except Exception as exc:
        safe = {
            "schema_version": "1.0.0",
            "status": "blocked",
            "environment": "dev",
            "reason": type(exc).__name__,
            "detail": str(exc)[:250],
            "runtime_sha": RUNTIME_SHA,
            "credential_rotated": False,
            "secret_value_exposed": False,
            "production_touched": False,
        }
        args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        return 4
    return 0 if evidence.get("status") == "passed" else 4


if __name__ == "__main__":
    raise SystemExit(main())
