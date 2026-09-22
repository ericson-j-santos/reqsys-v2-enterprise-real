#!/usr/bin/env python3
"""Concede, de forma idempotente e fail-closed, Contributor Fabric DEV à identidade OIDC governada."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EXPECTED_HOST = "NOTERI"
EXPECTED_TENANT = "6d09c88c-0617-490c-8329-305e577684bc"
WORKSPACE_NAME = "ReqSys - Observabilidade"
FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
ALLOWED_ROLES = {"Contributor", "Member", "Admin"}


class BootstrapError(RuntimeError):
    pass


def _run(args: list[str], timeout: int = 60) -> str:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )
    if proc.returncode != 0:
        raise BootstrapError(f"command_failed:{Path(args[0]).name}:{proc.returncode}")
    return (proc.stdout or "").strip()


def _find_az() -> str:
    for candidate in (
        shutil.which("az"),
        r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
    ):
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise BootstrapError("azure_cli_missing")


def _request_json(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return response.status, parsed if isinstance(parsed, dict) else {}
    except urllib.error.HTTPError as exc:
        # Nunca propagar corpo da resposta: pode conter identificadores ou detalhes de autorização.
        return exc.code, {}


def _fabric_token(az: str) -> str:
    token = _run([
        az,
        "account",
        "get-access-token",
        "--resource",
        "https://api.fabric.microsoft.com",
        "--query",
        "accessToken",
        "-o",
        "tsv",
        "--only-show-errors",
    ])
    if not token:
        raise BootstrapError("fabric_token_missing")
    return token


def _list_roles(workspace_id: str, token: str) -> tuple[int, list[dict[str, Any]]]:
    url = f"{FABRIC_BASE}/workspaces/{workspace_id}/roleAssignments"
    rows: list[dict[str, Any]] = []
    last_status = 0
    while url:
        status, payload = _request_json("GET", url, token)
        last_status = status
        if status != 200:
            return status, []
        rows.extend(row for row in payload.get("value", []) if isinstance(row, dict))
        continuation = str(payload.get("continuationUri") or "").strip()
        url = continuation if continuation.startswith("https://api.fabric.microsoft.com/") else ""
    return last_status, rows


def _target_assignments(
    rows: list[dict[str, Any]],
    *,
    sp_object_id: str,
    client_id: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        principal = row.get("principal") if isinstance(row.get("principal"), dict) else {}
        details = (
            principal.get("servicePrincipalDetails")
            if isinstance(principal.get("servicePrincipalDetails"), dict)
            else {}
        )
        same = (
            str(principal.get("id") or "").casefold() == sp_object_id.casefold()
            or str(details.get("aadAppId") or "").casefold() == client_id.casefold()
        )
        if same and str(principal.get("type") or "") == "ServicePrincipal":
            result.append(row)
    return result


def main() -> int:
    evidence_path = Path(
        os.environ.get(
            "EVIDENCE_FILE",
            "artifacts/report-factory/fabric-dev-access-bootstrap.json",
        )
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, Any] = {
        "schema": "report-factory-fabric-dev-access-bootstrap/v1",
        "status": "blocked",
        "environment": "development",
        "host_ok": False,
        "tenant_match": False,
        "service_principal_found": False,
        "workspace_exact_count": 0,
        "workspace_list_status": None,
        "role_assignments_before_status": None,
        "before_roles": [],
        "mutation": "none",
        "write_status": None,
        "role_assignments_after_status": None,
        "after_roles": [],
        "contributor_or_higher_after": False,
        "secret_value_exposed": False,
        "identifiers_exposed": False,
        "production_touched": False,
    }

    try:
        evidence["host_ok"] = platform.node().strip().upper() == EXPECTED_HOST
        if not evidence["host_ok"]:
            raise BootstrapError("unexpected_host")

        client_id = os.environ.get("CCP_AZURE_CLIENT_ID", "").strip()
        if not client_id:
            raise BootstrapError("ccp_client_id_missing")

        az = _find_az()
        account = json.loads(_run([az, "account", "show", "--output", "json"]))
        tenant = str(account.get("tenantId") or "")
        evidence["tenant_match"] = tenant.casefold() == EXPECTED_TENANT.casefold()
        if not evidence["tenant_match"]:
            raise BootstrapError("tenant_mismatch")

        sp = json.loads(_run([az, "ad", "sp", "show", "--id", client_id, "--output", "json"]))
        sp_object_id = str(sp.get("id") or "").strip()
        evidence["service_principal_found"] = bool(sp_object_id)
        if not sp_object_id:
            raise BootstrapError("service_principal_missing")

        token = _fabric_token(az)
        status, payload = _request_json("GET", f"{FABRIC_BASE}/workspaces", token)
        evidence["workspace_list_status"] = status
        if status != 200:
            raise BootstrapError(f"workspace_list_status:{status}")

        matches = [
            row
            for row in payload.get("value", [])
            if isinstance(row, dict)
            and str(row.get("displayName") or "") == WORKSPACE_NAME
        ]
        evidence["workspace_exact_count"] = len(matches)
        if len(matches) != 1:
            raise BootstrapError(f"workspace_exact_count:{len(matches)}")
        workspace_id = str(matches[0].get("id") or "").strip()
        if not workspace_id:
            raise BootstrapError("workspace_id_missing")

        before_status, before_rows = _list_roles(workspace_id, token)
        evidence["role_assignments_before_status"] = before_status
        if before_status != 200:
            raise BootstrapError(f"role_assignments_before_status:{before_status}")

        before_target = _target_assignments(
            before_rows,
            sp_object_id=sp_object_id,
            client_id=client_id,
        )
        if len(before_target) > 1:
            raise BootstrapError(f"ambiguous_target_assignments:{len(before_target)}")
        before_roles = sorted(
            {
                str(row.get("role") or "")
                for row in before_target
                if str(row.get("role") or "")
            }
        )
        evidence["before_roles"] = before_roles

        if any(role in ALLOWED_ROLES for role in before_roles):
            evidence["mutation"] = "noop"
        elif len(before_target) == 1:
            assignment_id = str(before_target[0].get("id") or "").strip()
            if not assignment_id:
                raise BootstrapError("existing_assignment_id_missing")
            write_status, _ = _request_json(
                "PATCH",
                f"{FABRIC_BASE}/workspaces/{workspace_id}/roleAssignments/{assignment_id}",
                token,
                {"role": "Contributor"},
            )
            evidence["write_status"] = write_status
            evidence["mutation"] = "updated"
            if write_status != 200:
                raise BootstrapError(f"role_update_status:{write_status}")
        else:
            write_status, _ = _request_json(
                "POST",
                f"{FABRIC_BASE}/workspaces/{workspace_id}/roleAssignments",
                token,
                {
                    "principal": {
                        "id": sp_object_id,
                        "type": "ServicePrincipal",
                    },
                    "role": "Contributor",
                },
            )
            evidence["write_status"] = write_status
            evidence["mutation"] = "created"
            if write_status != 201:
                raise BootstrapError(f"role_create_status:{write_status}")

        after_status, after_rows = _list_roles(workspace_id, token)
        evidence["role_assignments_after_status"] = after_status
        if after_status != 200:
            raise BootstrapError(f"role_assignments_after_status:{after_status}")

        after_target = _target_assignments(
            after_rows,
            sp_object_id=sp_object_id,
            client_id=client_id,
        )
        after_roles = sorted(
            {
                str(row.get("role") or "")
                for row in after_target
                if str(row.get("role") or "")
            }
        )
        evidence["after_roles"] = after_roles
        evidence["contributor_or_higher_after"] = any(
            role in ALLOWED_ROLES for role in after_roles
        )
        if not evidence["contributor_or_higher_after"]:
            raise BootstrapError("contributor_postcondition_failed")

        evidence["status"] = "ok"
        return 0
    except Exception as exc:
        evidence["reason"] = str(exc).splitlines()[0][:120]
        return 2
    finally:
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("REPORT_FACTORY_FABRIC_DEV_ACCESS_BOOTSTRAP")
        for key in (
            "status",
            "environment",
            "host_ok",
            "tenant_match",
            "service_principal_found",
            "workspace_exact_count",
            "workspace_list_status",
            "role_assignments_before_status",
            "before_roles",
            "mutation",
            "write_status",
            "role_assignments_after_status",
            "after_roles",
            "contributor_or_higher_after",
            "secret_value_exposed",
            "identifiers_exposed",
            "production_touched",
        ):
            print(f"{key}={evidence.get(key)}")
        if evidence.get("reason"):
            print(f"reason={evidence['reason']}")


if __name__ == "__main__":
    sys.exit(main())
