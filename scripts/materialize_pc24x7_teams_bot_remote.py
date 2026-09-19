#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from pc24x7_teams_ephemeral_e2e import (
    ADMIN_EMAIL_DEFAULT,
    EphemeralE2EError,
    _data,
    execute_e2e,
    request_json,
    resolve_admin_jwt,
)

EXPECTED_ENVIRONMENT = "dev"
EXPECTED_RUNTIME_TARGET = "pc24x7"
RESTART_CONFIRM = "RESTART-COFRE-DEV-RUNTIME"
BOT_KEYS = (
    "TEAMS_BOT_APP_ID",
    "TEAMS_BOT_APP_TENANT_ID",
    "TEAMS_BOT_SECRET",
)


class MaterializationError(RuntimeError):
    pass


def _headers(admin_jwt: str, correlation_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {admin_jwt}",
        "X-Correlation-Id": correlation_id,
        "Accept": "application/json",
    }


def _admin_call(
    method: str,
    api_base: str,
    path: str,
    admin_jwt: str,
    correlation_id: str,
    *,
    body: dict[str, Any] | None = None,
    expected: tuple[int, ...] = (200,),
) -> dict[str, Any]:
    status, payload = request_json(
        method,
        api_base.rstrip("/") + path,
        headers=_headers(admin_jwt, correlation_id),
        body=body,
    )
    if status not in expected:
        raise MaterializationError(f"http_{status}:{path}")
    data = _data(payload)
    if not isinstance(data, dict):
        raise MaterializationError(f"invalid_envelope:{path}")
    return data


def _validate_base_url(api_base: str) -> str:
    value = api_base.strip().rstrip("/")
    if not value.startswith("https://"):
        raise MaterializationError("pc24x7_base_url_must_use_https")
    lowered = value.lower()
    if "fly.io" in lowered or "fly.dev" in lowered:
        raise MaterializationError("fly_runtime_forbidden")
    return value


def _control_status(
    api_base: str,
    admin_jwt: str,
    correlation_id: str,
    expected_sha: str,
) -> dict[str, Any]:
    data = _admin_call(
        "GET",
        api_base,
        "/v1/cofre/runtime/control-status",
        admin_jwt,
        correlation_id,
    )
    if str(data.get("environment") or "").lower() != EXPECTED_ENVIRONMENT:
        raise MaterializationError("runtime_environment_not_dev")
    if data.get("runtime_target") != EXPECTED_RUNTIME_TARGET:
        raise MaterializationError("runtime_target_mismatch")
    if data.get("runtime_sha") != expected_sha:
        raise MaterializationError("runtime_sha_mismatch")
    if data.get("self_restart_enabled") is not True:
        raise MaterializationError("self_restart_not_enabled")
    boot_id = str(data.get("boot_id") or "")
    if not boot_id:
        raise MaterializationError("boot_id_missing")
    return {
        "runtime_sha": expected_sha,
        "boot_id": boot_id,
        "self_restart_enabled": True,
        "production_touched": False,
        "sensitive_values_exposed": False,
    }


def _check_vault_ready(
    api_base: str,
    admin_jwt: str,
    correlation_id: str,
) -> dict[str, Any]:
    data = _admin_call(
        "GET",
        api_base,
        "/v1/cofre/status",
        admin_jwt,
        correlation_id,
    )
    if data.get("inicializado") is not True:
        raise MaterializationError("cofre_not_initialized")
    return {
        "initialized": True,
        "service": data.get("service"),
        "secret_value_exposed": False,
    }


def _write_bot_secrets(
    api_base: str,
    admin_jwt: str,
    correlation_id: str,
    values: dict[str, str],
) -> list[str]:
    written: list[str] = []
    for key in BOT_KEYS:
        value = values.get(key, "")
        if not value:
            raise MaterializationError(f"credential_missing:{key}")
        data = _admin_call(
            "POST",
            api_base,
            "/v1/cofre/segredos",
            admin_jwt,
            f"{correlation_id}-write-{key.lower()}",
            body={"key": key, "value": value},
        )
        if data.get("key") != key or data.get("gravado") is not True:
            raise MaterializationError(f"cofre_write_not_confirmed:{key}")
        written.append(key)
    return written


def _restart_and_verify(
    api_base: str,
    admin_jwt: str,
    correlation_id: str,
    expected_sha: str,
    before_boot_id: str,
    wait_seconds: int,
) -> dict[str, Any]:
    result = _admin_call(
        "POST",
        api_base,
        "/v1/cofre/runtime/restart",
        admin_jwt,
        f"{correlation_id}-restart",
        body={"expected_sha": expected_sha, "confirm": RESTART_CONFIRM},
        expected=(202,),
    )
    if result.get("runtime_sha") != expected_sha:
        raise MaterializationError("restart_sha_mismatch")
    if result.get("production_touched") is not False:
        raise MaterializationError("restart_production_flag_invalid")
    if result.get("accepted") is not True and result.get("duplicate") is not True:
        raise MaterializationError("restart_not_accepted")

    deadline = time.monotonic() + wait_seconds
    last_error = "runtime_not_reachable"
    while time.monotonic() < deadline:
        try:
            current = _control_status(
                api_base,
                admin_jwt,
                f"{correlation_id}-verify",
                expected_sha,
            )
        except (MaterializationError, EphemeralE2EError) as exc:
            last_error = type(exc).__name__
            time.sleep(2)
            continue
        if current["boot_id"] != before_boot_id:
            return {
                "accepted": bool(result.get("accepted")),
                "duplicate": bool(result.get("duplicate")),
                "before_boot_id": before_boot_id,
                "after_boot_id": current["boot_id"],
                "boot_id_changed": True,
                "runtime_sha": expected_sha,
                "production_touched": False,
                "sensitive_values_exposed": False,
            }
        last_error = "boot_id_unchanged"
        time.sleep(2)
    raise MaterializationError(f"restart_verification_timeout:{last_error}")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    api_base = _validate_base_url(args.api_base)
    bot_secret = os.getenv("BOT_SECRET", "")
    bot_app_id = os.getenv("BOT_APP_ID", "")
    tenant_id = os.getenv("BOT_TENANT_ID", "")
    if not bot_secret:
        raise MaterializationError("credential_missing:TEAMS_BOT_SECRET")
    if not bot_app_id:
        raise MaterializationError("credential_missing:TEAMS_BOT_APP_ID")
    if not tenant_id:
        raise MaterializationError("credential_missing:TEAMS_BOT_APP_TENANT_ID")

    admin_jwt = ""
    evidence: dict[str, Any] = {
        "schema_version": "1.0.0",
        "status": "blocked",
        "environment": "dev",
        "runtime_target": "pc24x7",
        "runtime_sha": args.expected_sha,
        "correlation_id": args.correlation_id,
        "credential_source": "azure_key_vault_existing",
        "credential_rotated": False,
        "secret_value_exposed": False,
        "production_touched": False,
        "vault": None,
        "preflight": None,
        "keys_written": [],
        "restart": None,
        "e2e": None,
        "error": None,
    }
    try:
        admin_jwt, auth_source, recovered = resolve_admin_jwt(
            api_base,
            os.getenv("COFRE_ADMIN_JWT", ""),
            args.correlation_id,
            args.admin_email,
        )
        evidence["admin_auth_source"] = auth_source
        evidence["admin_auth_recovered"] = recovered

        evidence["vault"] = _check_vault_ready(
            api_base, admin_jwt, f"{args.correlation_id}-vault"
        )
        before = _control_status(
            api_base,
            admin_jwt,
            f"{args.correlation_id}-preflight",
            args.expected_sha,
        )
        evidence["preflight"] = before

        values = {
            "TEAMS_BOT_APP_ID": bot_app_id,
            "TEAMS_BOT_APP_TENANT_ID": tenant_id,
            "TEAMS_BOT_SECRET": bot_secret,
        }
        evidence["keys_written"] = _write_bot_secrets(
            api_base,
            admin_jwt,
            args.correlation_id,
            values,
        )
        values.clear()
        bot_secret = ""

        evidence["restart"] = _restart_and_verify(
            api_base,
            admin_jwt,
            args.correlation_id,
            args.expected_sha,
            str(before["boot_id"]),
            args.wait_seconds,
        )

        e2e = execute_e2e(
            api_base=api_base,
            admin_jwt=admin_jwt,
            correlation_id=f"{args.correlation_id}-e2e",
            provider=args.provider,
            model=args.model,
            admin_email=args.admin_email,
        )
        evidence["e2e"] = e2e
        delivered = any(
            isinstance(item, dict)
            and item.get("teams_delivered") is True
            and item.get("teams_channel") == "bot"
            for item in e2e.get("delivery_attempts", [])
        )
        passed = (
            e2e.get("status") == "done"
            and e2e.get("token_revoked") is True
            and (e2e.get("readiness") or {}).get("ready") is True
            and e2e.get("turn_idempotency_proven") is True
            and delivered
        )
        if not passed:
            raise MaterializationError("teams_e2e_not_proven")
        evidence["status"] = "passed"
        return evidence
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}:{str(exc)[:180]}"
        return evidence
    finally:
        bot_secret = ""
        admin_jwt = ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Materializa Teams Bot no Cofre persistente PC24x7 DEV")
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--wait-seconds", type=int, default=180)
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--admin-email", default=ADMIN_EMAIL_DEFAULT)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    if len(args.expected_sha) != 40 or any(c not in "0123456789abcdef" for c in args.expected_sha.lower()):
        raise SystemExit("expected-sha inválido")

    result = execute(args)
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result.get("status"),
        "environment": "dev",
        "runtime_sha": args.expected_sha,
        "keys_written": result.get("keys_written", []),
        "restart_ok": bool((result.get("restart") or {}).get("boot_id_changed")),
        "e2e_status": (result.get("e2e") or {}).get("status"),
        "secret_value_exposed": False,
        "production_touched": False,
        "error": result.get("error"),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "passed" else 4


if __name__ == "__main__":
    raise SystemExit(main())
