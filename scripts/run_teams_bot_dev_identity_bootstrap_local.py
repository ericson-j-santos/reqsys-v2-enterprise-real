#!/usr/bin/env python3
"""Executa de forma governada o bootstrap idempotente da identidade Teams Bot DEV."""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_HOST = "NOTERI"
TENANT_ENV = "CCP_AZURE_TENANT_ID"
BOOTSTRAP = Path("scripts/bootstrap_teams_bot_dev_identity.py")
CONFIRMATION = "CRIAR-IDENTIDADE-TEAMS-BOT-DEV"
GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class RunnerError(RuntimeError):
    pass


def _repo_relative(path: Path) -> Path:
    repo = Path.cwd().resolve()
    target = path.resolve()
    try:
        target.relative_to(repo)
    except ValueError as exc:
        raise RunnerError("output_path_outside_repo") from exc
    return target


def _read_json(path: Path, reason: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerError(reason) from exc
    if not isinstance(payload, dict):
        raise RunnerError(reason)
    return payload


def _run_bootstrap(output: Path, *, dry_run: bool) -> dict[str, Any]:
    tenant = str(os.environ.get(TENANT_ENV) or "").strip()
    if not GUID_RE.fullmatch(tenant):
        raise RunnerError("expected_tenant_missing_or_invalid")
    if not BOOTSTRAP.is_file():
        raise RunnerError("bootstrap_script_missing")

    output = _repo_relative(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable,
        str(BOOTSTRAP),
        "--confirm",
        CONFIRMATION,
        "--tenant-id",
        tenant,
        "--output",
        str(output),
    ]
    if dry_run:
        args.append("--dry-run")

    completed = subprocess.run(
        args,
        cwd=str(Path.cwd()),
        shell=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        check=False,
    )
    if completed.returncode != 0:
        raise RunnerError(f"bootstrap_failed_exit_{completed.returncode}")
    return _read_json(output, "bootstrap_evidence_invalid")


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    target = _repo_relative(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix="teams-bot-identity-", suffix=".json", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def execute(output: Path) -> dict[str, Any]:
    host = socket.gethostname().upper()
    if host != EXPECTED_HOST:
        raise RunnerError("unexpected_host")

    base = output.parent
    before = _run_bootstrap(base / "preflight.json", dry_run=True)
    if before.get("status") != "dry_run" or before.get("environment") != "dev":
        raise RunnerError("preflight_contract_mismatch")
    if before.get("secret_value_exposed") is not False:
        raise RunnerError("preflight_secret_contract_mismatch")

    applied = _run_bootstrap(base / "bootstrap.json", dry_run=False)
    if applied.get("status") != "ready" or applied.get("environment") != "dev":
        raise RunnerError("bootstrap_not_ready")
    if applied.get("secret_value_exposed") is not False:
        raise RunnerError("bootstrap_secret_contract_mismatch")

    after = _run_bootstrap(base / "readback.json", dry_run=True)
    expected_plan = ["nenhuma; identidade dedicada já está completa"]
    if after.get("status") != "dry_run" or after.get("planned_actions") != expected_plan:
        raise RunnerError("independent_readback_not_complete")
    if after.get("app_id") != applied.get("app_id") or not applied.get("app_id"):
        raise RunnerError("app_id_readback_mismatch")
    if after.get("secret_exists") is not True or after.get("secret_value_exposed") is not False:
        raise RunnerError("secret_readback_mismatch")

    changed = any(
        bool(applied.get(name))
        for name in ("created_app", "created_service_principal", "secret_created")
    )
    evidence = {
        "schema_version": "1.0.0",
        "status": "READY" if changed else "ALREADY_COMPLIANT",
        "environment": "dev",
        "host": host,
        "app_display_name": applied.get("app_display_name"),
        "app_id": applied.get("app_id"),
        "secret_store": applied.get("secret_store"),
        "secret_name": applied.get("secret_name"),
        "created_app": bool(applied.get("created_app")),
        "created_service_principal": bool(applied.get("created_service_principal")),
        "secret_created": bool(applied.get("secret_created")),
        "initial_planned_actions": before.get("planned_actions") or [],
        "post_planned_actions": after.get("planned_actions") or [],
        "independent_readback": True,
        "secret_value_exposed": False,
        "production_touched": False,
        "test_hml_stg_touched": False,
    }
    _atomic_write(output, evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap governado Teams Bot DEV no host Noteri")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = execute(args.output)
    except (RunnerError, OSError, subprocess.SubprocessError) as exc:
        reason = str(exc) if isinstance(exc, RunnerError) else exc.__class__.__name__
        try:
            _atomic_write(
                args.output,
                {
                    "schema_version": "1.0.0",
                    "status": "BLOCKED",
                    "reason": reason,
                    "environment": "dev",
                    "host": socket.gethostname().upper(),
                    "independent_readback": False,
                    "secret_value_exposed": False,
                    "production_touched": False,
                    "test_hml_stg_touched": False,
                },
            )
        except Exception:
            pass
        return 20
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
