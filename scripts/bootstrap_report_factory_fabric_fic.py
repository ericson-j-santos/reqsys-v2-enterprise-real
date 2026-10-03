#!/usr/bin/env python3
"""Bootstrap idempotente da FIC GitHub -> ReqSys ALM Pipeline para o Report Factory DEV."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

EXPECTED_HOST = "NOTERI"
EXPECTED_TENANT = "6d09c88c-0617-490c-8329-305e577684bc"
APP_NAME = "ReqSys ALM Pipeline"
CREDENTIAL_NAME = "reqsys-report-factory-development"
ISSUER = "https://token.actions.githubusercontent.com"
AUDIENCE = "api://AzureADTokenExchange"
SUBJECT = "repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:development"
CONFIRMATION = "CRIAR-FIC-REPORT-FACTORY-DEV"


class BootstrapError(RuntimeError):
    pass


def _az() -> str:
    for candidate in (
        shutil.which("az"),
        shutil.which("az.cmd"),
        r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
    ):
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise BootstrapError("azure_cli_missing")


def _run(az: str, args: list[str], timeout: int = 60) -> str:
    proc = subprocess.run(
        [az, *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )
    if proc.returncode != 0:
        raise BootstrapError(
            f"azure_cli_failed:{args[0] if args else 'unknown'}:{proc.returncode}"
        )
    return (proc.stdout or "").strip()


def _tenant(az: str) -> str:
    value = _run(az, ["account", "show", "--query", "tenantId", "--output", "tsv"])
    if not value:
        raise BootstrapError("azure_session_missing")
    if value.casefold() != EXPECTED_TENANT.casefold():
        raise BootstrapError("tenant_mismatch")
    return value


def _app_object_id(az: str) -> str:
    raw = _run(
        az,
        ["ad", "app", "list", "--display-name", APP_NAME, "--output", "json"],
    )
    rows = json.loads(raw or "[]")
    exact = [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("displayName") or "") == APP_NAME
    ]
    if len(exact) != 1:
        raise BootstrapError(f"app_exact_count:{len(exact)}")
    object_id = str(exact[0].get("id") or "")
    if not object_id:
        raise BootstrapError("app_object_id_missing")
    return object_id


def _list_fics(az: str, object_id: str) -> list[dict[str, Any]]:
    url = (
        "https://graph.microsoft.com/v1.0/applications/"
        + object_id
        + "/federatedIdentityCredentials?$select=name,issuer,subject,audiences"
    )
    raw = _run(
        az,
        ["rest", "--method", "GET", "--url", url, "--output", "json"],
    )
    payload = json.loads(raw or "{}")
    values = payload.get("value", []) if isinstance(payload, dict) else []
    if not isinstance(values, list):
        raise BootstrapError("fic_list_invalid")
    return [row for row in values if isinstance(row, dict)]


def _is_exact(row: dict[str, Any]) -> bool:
    return (
        str(row.get("name") or "") == CREDENTIAL_NAME
        and str(row.get("issuer") or "") == ISSUER
        and str(row.get("subject") or "") == SUBJECT
        and row.get("audiences") == [AUDIENCE]
    )


def _ensure_no_conflict(rows: list[dict[str, Any]]) -> None:
    exact = [row for row in rows if _is_exact(row)]
    if len(exact) > 1:
        raise BootstrapError("duplicate_exact_fic")
    for row in rows:
        same_name = str(row.get("name") or "") == CREDENTIAL_NAME
        same_subject = str(row.get("subject") or "") == SUBJECT
        if (same_name or same_subject) and not _is_exact(row):
            raise BootstrapError("fic_contract_conflict")


def bootstrap(*, apply: bool, confirm: str) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "schema": "report-factory-fabric-fic-bootstrap/v1",
        "status": "started",
        "host_ok": False,
        "tenant_match": False,
        "app_exact_count": 0,
        "fic_exact_count_before": 0,
        "fic_exact_count_after": 0,
        "created": False,
        "mutation_performed": False,
        "secret_value_exposed": False,
        "identifiers_exposed": False,
    }

    evidence["host_ok"] = platform.node().strip().upper() == EXPECTED_HOST
    if not evidence["host_ok"]:
        raise BootstrapError("unexpected_host")

    az = _az()
    _tenant(az)
    evidence["tenant_match"] = True
    object_id = _app_object_id(az)
    evidence["app_exact_count"] = 1

    before = _list_fics(az, object_id)
    _ensure_no_conflict(before)
    exact_before = [row for row in before if _is_exact(row)]
    evidence["fic_exact_count_before"] = len(exact_before)

    if len(exact_before) == 1:
        evidence["fic_exact_count_after"] = 1
        evidence["status"] = "ready"
        return evidence

    if not apply:
        evidence["status"] = "planned"
        return evidence

    if confirm != CONFIRMATION:
        raise BootstrapError("explicit_confirmation_required")

    body = json.dumps(
        {
            "name": CREDENTIAL_NAME,
            "issuer": ISSUER,
            "subject": SUBJECT,
            "description": "ReqSys Report Factory Fabric DEV; GitHub Environment development",
            "audiences": [AUDIENCE],
        },
        separators=(",", ":"),
    )
    url = (
        "https://graph.microsoft.com/v1.0/applications/"
        + object_id
        + "/federatedIdentityCredentials"
    )
    _run(
        az,
        [
            "rest",
            "--method",
            "POST",
            "--url",
            url,
            "--headers",
            "Content-Type=application/json",
            "--body",
            body,
            "--output",
            "none",
        ],
    )
    evidence["created"] = True
    evidence["mutation_performed"] = True

    after = _list_fics(az, object_id)
    _ensure_no_conflict(after)
    exact_after = [row for row in after if _is_exact(row)]
    evidence["fic_exact_count_after"] = len(exact_after)
    if len(exact_after) != 1:
        raise BootstrapError("fic_postcondition_failed")

    evidence["status"] = "ready"
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        evidence = bootstrap(apply=args.apply, confirm=args.confirm)
        rc = 0
    except (BootstrapError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        evidence = {
            "schema": "report-factory-fabric-fic-bootstrap/v1",
            "status": "blocked",
            "reason": str(exc).splitlines()[0][:160],
            "created": False,
            "mutation_performed": False,
            "secret_value_exposed": False,
            "identifiers_exposed": False,
        }
        rc = 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for key in (
        "status",
        "host_ok",
        "tenant_match",
        "app_exact_count",
        "fic_exact_count_before",
        "fic_exact_count_after",
        "created",
        "mutation_performed",
        "secret_value_exposed",
        "identifiers_exposed",
    ):
        print(f"{key}={evidence.get(key)}")
    if evidence.get("reason"):
        print(f"reason={evidence['reason']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
