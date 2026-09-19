#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

CONFIRMATION = "REUSE-EXISTING-TEAMS-BOT-DEV"
BOT_SECRET_NAME = "reqsys-teams-bot-dev-secret"


class ProvisionError(RuntimeError):
    pass


def _tool(name: str) -> str:
    for candidate in (name, f"{name}.exe", f"{name}.cmd", f"{name}.bat"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise ProvisionError(f"tool_missing:{name}")


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
    sensitive: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
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
            raise ProvisionError(f"sensitive_command_failed:{Path(args[0]).name}:exit_{result.returncode}")
        detail = (result.stderr or result.stdout or "sem detalhe").strip().replace("\n", " ")
        raise ProvisionError(f"command_failed:{Path(args[0]).name}:exit_{result.returncode}:{detail[:500]}")
    return result


def _git_head(repo: Path) -> str:
    return _run([_tool("git"), "-C", str(repo), "rev-parse", "HEAD"], timeout=30).stdout.strip()


def _azure_tenant() -> str:
    return _run(
        [_tool("az"), "account", "show", "--query", "tenantId", "--output", "tsv"],
        timeout=60,
    ).stdout.strip()


def _load_existing_bot_secret(vault_name: str, expected_tenant_id: str) -> tuple[str, str]:
    active_tenant = _azure_tenant()
    if not active_tenant or active_tenant.casefold() != expected_tenant_id.casefold():
        raise ProvisionError("azure_tenant_mismatch")

    result = _run(
        [
            _tool("az"),
            "keyvault",
            "secret",
            "show",
            "--vault-name",
            vault_name,
            "--name",
            BOT_SECRET_NAME,
            "--query",
            '{value:value,enabled:attributes.enabled,app_id:tags."app-id"}',
            "--output",
            "json",
            "--only-show-errors",
        ],
        timeout=90,
        sensitive=True,
    )
    try:
        payload: Any = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ProvisionError("keyvault_secret_payload_invalid") from exc
    if not isinstance(payload, dict):
        raise ProvisionError("keyvault_secret_payload_invalid")
    if payload.get("enabled") is False:
        raise ProvisionError("keyvault_secret_disabled")
    app_id = str(payload.get("app_id") or "").strip()
    secret_value = str(payload.get("value") or "")
    if not app_id:
        raise ProvisionError("keyvault_secret_app_id_tag_missing")
    if not secret_value:
        raise ProvisionError("keyvault_secret_value_missing")
    return app_id, secret_value


def _parse_json_stdout(result: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    for raw in reversed(lines):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ProvisionError(f"{label}_json_missing")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise ProvisionError(f"confirmation_required:{CONFIRMATION}")
    if args.environment != "dev":
        raise ProvisionError("environment_must_be_dev")

    runtime_root = args.runtime_repo_root.resolve()
    if not runtime_root.is_dir():
        raise ProvisionError("runtime_repo_missing")
    if _git_head(runtime_root) != args.expected_runtime_sha:
        raise ProvisionError("runtime_sha_mismatch")
    if not args.admin_override.is_file():
        raise ProvisionError("admin_override_missing")
    if not args.teams_override.is_file():
        raise ProvisionError("teams_override_missing")

    app_id, bot_secret = _load_existing_bot_secret(args.vault_name, args.expected_tenant_id)
    child_env = os.environ.copy()
    child_env["TEAMS_BOT_APP_ID"] = app_id
    child_env["TEAMS_BOT_APP_TENANT_ID"] = args.expected_tenant_id
    child_env["TEAMS_BOT_SECRET"] = bot_secret

    recreate = _run(
        [
            sys.executable,
            str(runtime_root / "scripts" / "recreate_cofre_dev_pc24x7.py"),
            "--repo-root",
            str(runtime_root),
            "--expected-sha",
            args.expected_runtime_sha,
            "--admin-override",
            str(args.admin_override.resolve()),
            "--teams-override",
            str(args.teams_override.resolve()),
            "--health-timeout",
            "240",
        ],
        cwd=runtime_root,
        env=child_env,
        timeout=720,
        sensitive=True,
    )
    recreate_evidence = _parse_json_stdout(recreate, "recreate")

    child_env["TEAMS_BOT_SECRET"] = ""
    bot_secret = ""

    e2e_path = args.evidence_file.with_name("teams-bot-runtime-e2e-detail.json")
    e2e = _run(
        [
            sys.executable,
            str(runtime_root / "scripts" / "pc24x7_teams_ephemeral_e2e.py"),
            "--api-base",
            "http://127.0.0.1:8210",
            "--correlation-id",
            args.correlation_id,
            "--evidence-path",
            str(e2e_path.resolve()),
        ],
        cwd=runtime_root,
        env=child_env,
        timeout=600,
        sensitive=False,
    )
    e2e_evidence = _parse_json_stdout(e2e, "e2e")

    delivered = any(
        isinstance(item, dict)
        and item.get("teams_delivered") is True
        and item.get("teams_channel") == "bot"
        for item in e2e_evidence.get("delivery_attempts", [])
    )
    passed = bool(
        e2e_evidence.get("status") == "done"
        and e2e_evidence.get("token_revoked") is True
        and (e2e_evidence.get("readiness") or {}).get("ready") is True
        and e2e_evidence.get("turn_idempotency_proven") is True
        and delivered
    )

    evidence = {
        "schema_version": "1.0.0",
        "status": "passed" if passed else "blocked",
        "environment": "dev",
        "runtime_sha": args.expected_runtime_sha,
        "correlation_id": args.correlation_id,
        "credential_source": "azure_key_vault_existing",
        "credential_rotated": False,
        "secret_value_exposed": False,
        "production_touched": False,
        "recreate": recreate_evidence,
        "e2e": e2e_evidence,
    }
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--environment", default="dev")
    parser.add_argument("--runtime-repo-root", type=Path, required=True)
    parser.add_argument("--expected-runtime-sha", required=True)
    parser.add_argument("--vault-name", required=True)
    parser.add_argument("--expected-tenant-id", required=True)
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
            "detail": str(exc)[:300],
            "credential_rotated": False,
            "secret_value_exposed": False,
            "production_touched": False,
        }
        args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.write_text(
            json.dumps(safe, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        return 4
    return 0 if evidence.get("status") == "passed" else 4


if __name__ == "__main__":
    raise SystemExit(main())
