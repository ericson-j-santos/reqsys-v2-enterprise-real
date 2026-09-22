#!/usr/bin/env python3
"""Probe read-only da autorização Fabric HML da service principal alvo."""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

EXPECTED_HOST = "NOTERI"
TENANT_ID = "6d09c88c-0617-490c-8329-305e577684bc"
APP_NAME = "ReqSys ALM Pipeline"
WORKSPACE_NAME = "ReqSys - Observabilidade"


class ProbeError(RuntimeError):
    pass


def run(args: list[str], timeout: int = 60) -> str:
    proc = subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, shell=False
    )
    if proc.returncode != 0:
        raise ProbeError(f"command_failed:{Path(args[0]).name}:{proc.returncode}")
    return proc.stdout.strip()


def find_az() -> str:
    for candidate in (
        shutil.which("az"),
        r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
    ):
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise ProbeError("azure_cli_missing")


def fabric_token(az: str) -> str:
    token = run([
        az, "account", "get-access-token",
        "--resource", "https://api.fabric.microsoft.com",
        "--query", "accessToken", "-o", "tsv",
    ])
    if not token:
        raise ProbeError("fabric_user_token_missing")
    return token


def get_json(url: str, token: str) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def main() -> int:
    evidence_path = Path(
        "artifacts/fabric-hml-authorization-probe/evidence.json"
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema": "fabric-hml-authorization-probe/v1",
        "status": "blocked",
        "host_ok": False,
        "tenant_match": False,
        "app_exact_count": 0,
        "service_principal_found": False,
        "workspace_exact_count": 0,
        "role_assignments_status": None,
        "target_role_assignment_count": 0,
        "target_roles": [],
        "contributor_or_higher": False,
        "credential_metadata_count": 0,
        "bootstrap_credential_present": False,
        "tenant_settings_status": None,
        "service_principal_api_setting_found": False,
        "service_principal_api_setting_enabled": None,
        "service_principal_api_setting_scoped_group_count": 0,
        "secret_value_exposed": False,
        "identifiers_exposed": False,
    }
    try:
        evidence["host_ok"] = platform.node().strip().upper() == EXPECTED_HOST
        if not evidence["host_ok"]:
            raise ProbeError("unexpected_host")

        az = find_az()
        account = json.loads(run([az, "account", "show", "-o", "json"]))
        tenant = str(account.get("tenantId") or "")
        evidence["tenant_match"] = tenant.casefold() == TENANT_ID.casefold()
        if not evidence["tenant_match"]:
            raise ProbeError("tenant_mismatch")

        apps = json.loads(run([
            az, "ad", "app", "list",
            "--display-name", APP_NAME,
            "-o", "json",
        ]))
        exact_apps = [
            row for row in apps
            if str(row.get("displayName") or "") == APP_NAME
        ]
        evidence["app_exact_count"] = len(exact_apps)
        if len(exact_apps) != 1:
            raise ProbeError(f"app_exact_count:{len(exact_apps)}")
        app_id = str(exact_apps[0].get("appId") or "")
        if not app_id:
            raise ProbeError("app_id_missing")

        sp = json.loads(run([az, "ad", "sp", "show", "--id", app_id, "-o", "json"]))
        sp_object_id = str(sp.get("id") or "")
        evidence["service_principal_found"] = bool(sp_object_id)
        if not sp_object_id:
            raise ProbeError("service_principal_missing")

        credentials = json.loads(
            run([az, "ad", "app", "credential", "list", "--id", app_id, "-o", "json"])
            or "[]"
        )
        evidence["credential_metadata_count"] = len(credentials)
        evidence["bootstrap_credential_present"] = any(
            str(row.get("displayName") or "").startswith("painel-powerbi-hml-")
            for row in credentials
        )

        token = fabric_token(az)
        status, payload = get_json(
            "https://api.fabric.microsoft.com/v1/workspaces", token
        )
        if status != 200:
            raise ProbeError(f"workspace_list_status:{status}")
        exact_ws = [
            row for row in payload.get("value", [])
            if str(row.get("displayName") or "") == WORKSPACE_NAME
        ]
        evidence["workspace_exact_count"] = len(exact_ws)
        if len(exact_ws) != 1:
            raise ProbeError(f"workspace_exact_count:{len(exact_ws)}")
        workspace_id = str(exact_ws[0].get("id") or "")
        if not workspace_id:
            raise ProbeError("workspace_id_missing")

        roles: list[dict] = []
        url = (
            "https://api.fabric.microsoft.com/v1/workspaces/"
            + workspace_id
            + "/roleAssignments"
        )
        while url:
            role_status, role_payload = get_json(url, token)
            evidence["role_assignments_status"] = role_status
            if role_status != 200:
                raise ProbeError(f"role_assignments_status:{role_status}")
            roles.extend(
                row for row in role_payload.get("value", [])
                if isinstance(row, dict)
            )
            next_url = str(role_payload.get("continuationUri") or "").strip()
            url = next_url if next_url.startswith("https://api.fabric.microsoft.com/") else ""

        target = []
        for row in roles:
            principal = row.get("principal") if isinstance(row.get("principal"), dict) else {}
            details = (
                principal.get("servicePrincipalDetails")
                if isinstance(principal.get("servicePrincipalDetails"), dict)
                else {}
            )
            same = (
                str(principal.get("id") or "").casefold() == sp_object_id.casefold()
                or str(details.get("aadAppId") or "").casefold() == app_id.casefold()
            )
            if same and str(principal.get("type") or "") == "ServicePrincipal":
                target.append(row)

        target_roles = sorted({
            str(row.get("role") or "")
            for row in target
            if str(row.get("role") or "")
        })
        evidence["target_role_assignment_count"] = len(target)
        evidence["target_roles"] = target_roles
        evidence["contributor_or_higher"] = any(
            role in {"Contributor", "Member", "Admin"} for role in target_roles
        )

        tenant_rows: list[dict] = []
        tenant_url = "https://api.fabric.microsoft.com/v1/admin/tenantsettings"
        while tenant_url:
            tenant_status, tenant_payload = get_json(tenant_url, token)
            evidence["tenant_settings_status"] = tenant_status
            if tenant_status != 200:
                break
            tenant_rows.extend(
                row for row in tenant_payload.get("value", [])
                if isinstance(row, dict)
            )
            next_tenant_url = str(
                tenant_payload.get("continuationUri") or ""
            ).strip()
            tenant_url = (
                next_tenant_url
                if next_tenant_url.startswith("https://api.fabric.microsoft.com/")
                else ""
            )

        if evidence["tenant_settings_status"] == 200:
            candidates = []
            for row in tenant_rows:
                title = str(row.get("title") or "").casefold()
                setting_name = str(row.get("settingName") or "").casefold()
                if (
                    ("service principal" in title and "fabric" in title and "api" in title)
                    or ("serviceprincipal" in setting_name and "api" in setting_name)
                ):
                    candidates.append(row)
            if len(candidates) == 1:
                setting = candidates[0]
                evidence["service_principal_api_setting_found"] = True
                evidence["service_principal_api_setting_enabled"] = bool(
                    setting.get("enabled")
                )
                evidence["service_principal_api_setting_scoped_group_count"] = len(
                    setting.get("enabledSecurityGroups") or []
                )

        evidence["status"] = "ok"
        return 0
    except Exception as exc:
        evidence["reason"] = str(exc).splitlines()[0][:160]
        return 2
    finally:
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("FABRIC_HML_AUTHORIZATION_PROBE")
        for key in (
            "status",
            "host_ok",
            "tenant_match",
            "app_exact_count",
            "service_principal_found",
            "workspace_exact_count",
            "role_assignments_status",
            "target_role_assignment_count",
            "target_roles",
            "contributor_or_higher",
            "credential_metadata_count",
            "bootstrap_credential_present",
            "tenant_settings_status",
            "service_principal_api_setting_found",
            "service_principal_api_setting_enabled",
            "service_principal_api_setting_scoped_group_count",
            "secret_value_exposed",
            "identifiers_exposed",
        ):
            print(f"{key}={evidence.get(key)}")
        if evidence.get("reason"):
            print(f"reason={evidence['reason']}")


if __name__ == "__main__":
    sys.exit(main())
