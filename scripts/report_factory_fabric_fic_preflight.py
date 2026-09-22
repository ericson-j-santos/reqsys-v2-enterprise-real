#!/usr/bin/env python3
"""Preflight somente leitura da FIC OIDC do Report Factory no Fabric DEV."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EXPECTED_HOST = "NOTERI"
EXPECTED_TENANT = "6d09c88c-0617-490c-8329-305e577684bc"
APP_NAME = "ReqSys ALM Pipeline"
WORKSPACE_NAME = "ReqSys - Observabilidade"
CREDENTIAL_NAME = "reqsys-report-factory-development"
ISSUER = "https://token.actions.githubusercontent.com"
AUDIENCE = "api://AzureADTokenExchange"
SUBJECT = "repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:development"


class ProbeError(RuntimeError):
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
    raise ProbeError("azure_cli_missing")


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
        raise ProbeError(f"azure_cli_failed:{args[0] if args else 'unknown'}:{proc.returncode}")
    return (proc.stdout or "").strip()


def _get_json(url: str, token: str) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return response.status, payload if isinstance(payload, dict) else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def _token(az: str, resource: str) -> str:
    token = _run(
        az,
        [
            "account",
            "get-access-token",
            "--resource",
            resource,
            "--query",
            "accessToken",
            "--output",
            "tsv",
            "--only-show-errors",
        ],
    )
    if not token:
        raise ProbeError("access_token_empty")
    return token


def _exact_fic(item: dict[str, Any]) -> bool:
    return (
        str(item.get("name") or "") == CREDENTIAL_NAME
        and str(item.get("issuer") or "") == ISSUER
        and str(item.get("subject") or "") == SUBJECT
        and item.get("audiences") == [AUDIENCE]
    )


def run_probe(output: Path) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "schema": "report-factory-fabric-fic-preflight/v1",
        "status": "started",
        "host_ok": False,
        "tenant_match": False,
        "app_exact_count": 0,
        "workspace_exact_count": 0,
        "role_assignments_status": None,
        "target_role_assignment_count": 0,
        "target_roles": [],
        "contributor_or_higher": False,
        "fic_list_status": None,
        "fic_exact_count": 0,
        "fic_ready": False,
        "mutation_performed": False,
        "secret_value_exposed": False,
        "identifiers_exposed": False,
    }

    az = _az()
    evidence["host_ok"] = platform.node().strip().upper() == EXPECTED_HOST
    if not evidence["host_ok"]:
        raise ProbeError("unexpected_host")

    tenant = _run(az, ["account", "show", "--query", "tenantId", "--output", "tsv"])
    evidence["tenant_match"] = tenant.casefold() == EXPECTED_TENANT.casefold()
    if not evidence["tenant_match"]:
        raise ProbeError("tenant_mismatch")

    apps = json.loads(
        _run(
            az,
            ["ad", "app", "list", "--display-name", APP_NAME, "--output", "json"],
        )
        or "[]"
    )
    exact_apps = [
        row for row in apps
        if isinstance(row, dict) and str(row.get("displayName") or "") == APP_NAME
    ]
    evidence["app_exact_count"] = len(exact_apps)
    if len(exact_apps) != 1:
        raise ProbeError(f"app_exact_count:{len(exact_apps)}")

    app_object_id = str(exact_apps[0].get("id") or "")
    app_id = str(exact_apps[0].get("appId") or "")
    if not app_object_id or not app_id:
        raise ProbeError("app_identifier_missing")

    sp = json.loads(
        _run(az, ["ad", "sp", "show", "--id", app_id, "--output", "json"]) or "{}"
    )
    sp_object_id = str(sp.get("id") or "")
    if not sp_object_id:
        raise ProbeError("service_principal_missing")

    graph_token = _token(az, "https://graph.microsoft.com")
    fic_url = (
        "https://graph.microsoft.com/v1.0/applications/"
        + app_object_id
        + "/federatedIdentityCredentials?$select=name,issuer,subject,audiences"
    )
    fic_status, fic_payload = _get_json(fic_url, graph_token)
    evidence["fic_list_status"] = fic_status
    if fic_status != 200:
        raise ProbeError(f"fic_list_status:{fic_status}")
    fics = [item for item in fic_payload.get("value", []) if isinstance(item, dict)]
    exact_fics = [item for item in fics if _exact_fic(item)]
    evidence["fic_exact_count"] = len(exact_fics)
    evidence["fic_ready"] = len(exact_fics) == 1

    fabric_token = _token(az, "https://api.fabric.microsoft.com")
    workspace_status, workspace_payload = _get_json(
        "https://api.fabric.microsoft.com/v1/workspaces",
        fabric_token,
    )
    if workspace_status != 200:
        raise ProbeError(f"workspace_list_status:{workspace_status}")
    exact_workspaces = [
        row
        for row in workspace_payload.get("value", [])
        if isinstance(row, dict) and str(row.get("displayName") or "") == WORKSPACE_NAME
    ]
    evidence["workspace_exact_count"] = len(exact_workspaces)
    if len(exact_workspaces) != 1:
        raise ProbeError(f"workspace_exact_count:{len(exact_workspaces)}")
    workspace_id = str(exact_workspaces[0].get("id") or "")
    if not workspace_id:
        raise ProbeError("workspace_id_missing")

    role_status, role_payload = _get_json(
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/roleAssignments",
        fabric_token,
    )
    evidence["role_assignments_status"] = role_status
    if role_status != 200:
        raise ProbeError(f"role_assignments_status:{role_status}")

    target_roles: list[str] = []
    for row in role_payload.get("value", []):
        if not isinstance(row, dict):
            continue
        principal = row.get("principal") if isinstance(row.get("principal"), dict) else {}
        details = (
            principal.get("servicePrincipalDetails")
            if isinstance(principal.get("servicePrincipalDetails"), dict)
            else {}
        )
        same_principal = (
            str(principal.get("id") or "").casefold() == sp_object_id.casefold()
            or str(details.get("aadAppId") or "").casefold() == app_id.casefold()
        )
        if same_principal and str(principal.get("type") or "") == "ServicePrincipal":
            role = str(row.get("role") or "")
            if role:
                target_roles.append(role)

    evidence["target_roles"] = sorted(set(target_roles))
    evidence["target_role_assignment_count"] = len(target_roles)
    evidence["contributor_or_higher"] = any(
        role in {"Contributor", "Member", "Admin"} for role in target_roles
    )
    evidence["status"] = "ok"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        evidence = run_probe(args.output)
    except (ProbeError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        evidence = {
            "schema": "report-factory-fabric-fic-preflight/v1",
            "status": "blocked",
            "reason": str(exc).splitlines()[0][:160],
            "mutation_performed": False,
            "secret_value_exposed": False,
            "identifiers_exposed": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print("REPORT_FACTORY_FABRIC_FIC_PREFLIGHT")
    for key in (
        "status",
        "host_ok",
        "tenant_match",
        "app_exact_count",
        "workspace_exact_count",
        "role_assignments_status",
        "target_role_assignment_count",
        "target_roles",
        "contributor_or_higher",
        "fic_list_status",
        "fic_exact_count",
        "fic_ready",
        "mutation_performed",
        "secret_value_exposed",
        "identifiers_exposed",
    ):
        print(f"{key}={evidence.get(key)}")
    if evidence.get("reason"):
        print(f"reason={evidence['reason']}")
    return 0 if evidence.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
