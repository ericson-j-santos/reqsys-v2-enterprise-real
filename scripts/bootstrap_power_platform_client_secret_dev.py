#!/usr/bin/env python3
"""Rotaciona de forma governada o client secret Power Platform DEV.

A credencial é criada no Microsoft Entra, permanece apenas em memória e é
transmitida ao GitHub CLI por stdin. O valor nunca é aceito por argumento,
impresso, gravado em arquivo ou incluído na evidência.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from typing import Any

REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
ENVIRONMENT = "reqsys-power-platform-dev"
SECRET_NAME = "POWER_PLATFORM_CLIENT_SECRET"
WORKFLOW_FILE = "integration-excel-sql-sharepoint-functional-evidence-dev.yml"
CONFIRMATION = "ROTATE-POWER-PLATFORM-CLIENT-SECRET-DEV"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


class RotationError(RuntimeError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _tool(name: str) -> str:
    for candidate in (name, f"{name}.exe", f"{name}.cmd", f"{name}.bat"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RotationError(f"tool_missing:{name}")


def _run(tool: str, args: list[str], *, stdin: str | None = None, sensitive: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [_tool(tool), *args],
        input=stdin,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        if sensitive:
            raise RotationError(f"{tool}_sensitive_operation_failed")
        detail = (result.stderr or result.stdout or "sem detalhe").strip().replace("\n", " ")
        raise RotationError(f"{tool}_failed:{detail[:600]}")
    return result


def _az_json(args: list[str], *, sensitive: bool = False) -> Any:
    raw = _run("az", args, sensitive=sensitive).stdout or "null"
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RotationError("azure_json_invalid") from exc


def _az_tsv(args: list[str]) -> str:
    return (_run("az", args).stdout or "").strip()


def _graph(method: str, url: str, body: dict[str, Any] | None = None, *, sensitive: bool = False) -> Any:
    args = ["rest", "--method", method, "--url", url, "--output", "json"]
    if body is not None:
        args += ["--headers", "Content-Type=application/json", "--body", json.dumps(body, separators=(",", ":"))]
    return _az_json(args, sensitive=sensitive)


def _resolve_app(client_id: str, tenant_id: str) -> tuple[str, str]:
    active_tenant = _az_tsv(["account", "show", "--query", "tenantId", "--output", "tsv"])
    if not active_tenant:
        raise RotationError("azure_session_missing")
    if active_tenant.casefold() != tenant_id.casefold():
        raise RotationError("tenant_mismatch")
    app_object_id = _az_tsv(["ad", "app", "show", "--id", client_id, "--query", "id", "--output", "tsv"])
    display_name = _az_tsv(["ad", "app", "show", "--id", client_id, "--query", "displayName", "--output", "tsv"])
    if not app_object_id:
        raise RotationError("entra_application_not_found")
    return app_object_id, display_name


def _github_ready(repository: str) -> None:
    _run("gh", ["auth", "status", "--hostname", "github.com"])
    _run("gh", ["repo", "view", repository, "--json", "nameWithOwner"])


def _credential_name(correlation_id: str) -> str:
    digest = hashlib.sha256(correlation_id.encode("utf-8")).hexdigest()[:12]
    return f"reqsys-power-platform-dev-{digest}"


def _password_credentials(app_object_id: str) -> list[dict[str, Any]]:
    payload = _graph("GET", f"{GRAPH_ROOT}/applications/{app_object_id}?$select=passwordCredentials")
    values = payload.get("passwordCredentials") if isinstance(payload, dict) else []
    return [item for item in (values or []) if isinstance(item, dict)]


def _find_rotation(app_object_id: str, display_name: str) -> dict[str, Any] | None:
    return next((item for item in _password_credentials(app_object_id) if str(item.get("displayName") or "") == display_name), None)


def _add_password(app_object_id: str, display_name: str, days_valid: int) -> tuple[str, str]:
    end = (utcnow() + timedelta(days=days_valid)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = _graph(
        "POST",
        f"{GRAPH_ROOT}/applications/{app_object_id}/addPassword",
        {"passwordCredential": {"displayName": display_name, "endDateTime": end}},
        sensitive=True,
    )
    secret = str(payload.get("secretText") or "") if isinstance(payload, dict) else ""
    key_id = str(payload.get("keyId") or "") if isinstance(payload, dict) else ""
    if not secret or not key_id:
        raise RotationError("entra_add_password_incomplete")
    return secret, key_id


def _remove_password(app_object_id: str, key_id: str) -> None:
    _graph("POST", f"{GRAPH_ROOT}/applications/{app_object_id}/removePassword", {"keyId": key_id})


def _set_github_secret(repository: str, environment: str, secret_name: str, secret_value: str) -> None:
    # Sem --body: o valor entra exclusivamente via stdin e não aparece na linha de comando.
    _run(
        "gh",
        ["secret", "set", secret_name, "--env", environment, "--repo", repository],
        stdin=secret_value,
        sensitive=True,
    )


def _verify_github_secret(repository: str, environment: str, secret_name: str) -> dict[str, str]:
    payload = _run(
        "gh",
        ["api", f"repos/{repository}/environments/{environment}/secrets", "--jq", f'.secrets[] | select(.name=="{secret_name}") | {{name:name,updated_at:updated_at}}'],
    ).stdout.strip()
    if not payload:
        raise RotationError("github_secret_not_observed_after_write")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RotationError("github_secret_verification_invalid") from exc
    if data.get("name") != secret_name:
        raise RotationError("github_secret_name_mismatch")
    return {"name": secret_name, "updated_at": str(data.get("updated_at") or "")}


def _main_sha(repository: str) -> str:
    return (_run("gh", ["api", f"repos/{repository}/commits/main", "--jq", ".sha"]).stdout or "").strip()


def _dispatch_validation(repository: str, expected_sha: str) -> dict[str, Any]:
    started = utcnow().isoformat()
    _run("gh", ["workflow", "run", WORKFLOW_FILE, "--repo", repository, "--ref", "main"])
    for _ in range(24):
        time.sleep(5)
        rows = json.loads((_run("gh", ["run", "list", "--repo", repository, "--workflow", WORKFLOW_FILE, "--branch", "main", "--event", "workflow_dispatch", "--limit", "20", "--json", "databaseId,headSha,status,conclusion,createdAt,url"]).stdout or "[]"))
        run = next((item for item in rows if item.get("headSha") == expected_sha and str(item.get("createdAt") or "") >= started), None)
        if run:
            return {"run_id": int(run["databaseId"]), "head_sha": expected_sha, "status": run.get("status"), "url": run.get("url")}
    raise RotationError("validation_workflow_run_not_found")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise RotationError(f"confirmation_required:{CONFIRMATION}")
    if args.environment != ENVIRONMENT or args.secret_name != SECRET_NAME:
        raise RotationError("dev_scope_violation")
    if not 1 <= args.days_valid <= 365:
        raise RotationError("days_valid_out_of_range")

    app_object_id, app_name = _resolve_app(args.client_id, args.tenant_id)
    _github_ready(args.repository)
    display_name = _credential_name(args.correlation_id)
    existing = _find_rotation(app_object_id, display_name)
    if existing:
        return {
            "status": "blocked",
            "reason": "ROTATION_ALREADY_EXISTS",
            "environment": args.environment,
            "correlation_id": args.correlation_id,
            "credential_display_name": display_name,
            "secret_value_exposed": False,
        }
    if args.dry_run:
        return {
            "status": "dry_run",
            "environment": args.environment,
            "correlation_id": args.correlation_id,
            "application_name": app_name,
            "planned_action": "entra_add_password_then_github_environment_secret_then_validation_dispatch",
            "secret_value_exposed": False,
        }

    secret_value = ""
    key_id = ""
    github_evidence: dict[str, str] | None = None
    try:
        secret_value, key_id = _add_password(app_object_id, display_name, args.days_valid)
        _set_github_secret(args.repository, args.environment, args.secret_name, secret_value)
        github_evidence = _verify_github_secret(args.repository, args.environment, args.secret_name)
    except Exception:
        if key_id and not github_evidence:
            try:
                _remove_password(app_object_id, key_id)
            except Exception:
                pass
        raise
    finally:
        secret_value = ""

    main_sha = _main_sha(args.repository)
    if not main_sha:
        raise RotationError("main_sha_missing")
    validation = None if args.skip_validation_dispatch else _dispatch_validation(args.repository, main_sha)
    return {
        "status": "rotated",
        "environment": args.environment,
        "correlation_id": args.correlation_id,
        "application_name": app_name,
        "credential_display_name": display_name,
        "credential_key_present": bool(key_id),
        "github_secret": github_evidence,
        "validation": validation,
        "secret_value_exposed": False,
        "existing_credentials_deleted": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rotação segura do POWER_PLATFORM_CLIENT_SECRET em DEV")
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--repository", default=REPOSITORY)
    parser.add_argument("--environment", default=ENVIRONMENT)
    parser.add_argument("--secret-name", default=SECRET_NAME)
    parser.add_argument("--days-valid", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-validation-dispatch", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        result = execute(parse_args(argv))
    except RotationError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc), "environment": ENVIRONMENT, "secret_value_exposed": False}, ensure_ascii=False, sort_keys=True))
        return 4
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"rotated", "dry_run"} else 5


if __name__ == "__main__":
    raise SystemExit(main())
