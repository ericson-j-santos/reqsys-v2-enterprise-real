#!/usr/bin/env python3
"""Grant governado e idempotente de Contributor no Fabric HML."""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from fabric_hml_authorization_probe_temp import (
    APP_NAME,
    EXPECTED_HOST,
    TENANT_ID,
    WORKSPACE_NAME,
    ProbeError,
    fabric_token,
    find_az,
    get_json,
    run,
)

CONFIRMATION = "GRANT-FABRIC-HML-CONTRIBUTOR"
TARGET_ROLE = "Contributor"
FABRIC_ROOT = "https://api.fabric.microsoft.com/v1"


class ApplyError(RuntimeError):
    pass


def request_json(method: str, url: str, token: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def list_role_assignments(workspace_id: str, token: str) -> tuple[int, list[dict]]:
    roles: list[dict] = []
    url = f"{FABRIC_ROOT}/workspaces/{workspace_id}/roleAssignments"
    last_status = 0
    while url:
        last_status, payload = get_json(url, token)
        if last_status != 200:
            return last_status, []
        roles.extend(
            row for row in payload.get("value", [])
            if isinstance(row, dict)
        )
        next_url = str(payload.get("continuationUri") or "").strip()
        url = next_url if next_url.startswith(FABRIC_ROOT + "/") else ""
    return last_status, roles


def target_assignments(roles: list[dict], sp_object_id: str, app_id: str) -> list[dict]:
    found: list[dict] = []
    for row in roles:
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
            found.append(row)
    return found


def discover_target() -> tuple[str, str, str, str]:
    if platform.node().strip().upper() != EXPECTED_HOST:
        raise ApplyError("unexpected_host")

    az = find_az()
    account = json.loads(run([az, "account", "show", "-o", "json"]))
    tenant = str(account.get("tenantId") or "")
    if tenant.casefold() != TENANT_ID.casefold():
        raise ApplyError("tenant_mismatch")

    apps = json.loads(run([
        az, "ad", "app", "list",
        "--display-name", APP_NAME,
        "-o", "json",
    ]))
    exact_apps = [
        row for row in apps
        if str(row.get("displayName") or "") == APP_NAME
    ]
    if len(exact_apps) != 1:
        raise ApplyError(f"app_exact_count:{len(exact_apps)}")
    app_id = str(exact_apps[0].get("appId") or "")
    if not app_id:
        raise ApplyError("app_id_missing")

    sp = json.loads(run([az, "ad", "sp", "show", "--id", app_id, "-o", "json"]))
    sp_object_id = str(sp.get("id") or "")
    if not sp_object_id:
        raise ApplyError("service_principal_missing")

    token = fabric_token(az)
    status, payload = get_json(f"{FABRIC_ROOT}/workspaces", token)
    if status != 200:
        raise ApplyError(f"workspace_list_status:{status}")
    exact_ws = [
        row for row in payload.get("value", [])
        if str(row.get("displayName") or "") == WORKSPACE_NAME
    ]
    if len(exact_ws) != 1:
        raise ApplyError(f"workspace_exact_count:{len(exact_ws)}")
    workspace_id = str(exact_ws[0].get("id") or "")
    if not workspace_id:
        raise ApplyError("workspace_id_missing")

    return token, workspace_id, sp_object_id, app_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()

    evidence_path = Path("artifacts/fabric-hml-role-assignment/evidence.json")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema": "fabric-hml-role-assignment/v1",
        "status": "blocked",
        "target_role": TARGET_ROLE,
        "host_ok": False,
        "tenant_match": False,
        "app_exact": False,
        "service_principal_found": False,
        "workspace_exact": False,
        "pre_assignment_count": None,
        "pre_roles": [],
        "mutation_performed": False,
        "mutation_kind": "none",
        "mutation_status": None,
        "verification_assignment_count": None,
        "verification_roles": [],
        "postcondition_ok": False,
        "production_touched": False,
        "secret_value_exposed": False,
        "identifiers_exposed": False,
    }

    try:
        if args.confirm != CONFIRMATION:
            raise ApplyError("confirmation_mismatch")

        evidence["host_ok"] = platform.node().strip().upper() == EXPECTED_HOST
        token, workspace_id, sp_object_id, app_id = discover_target()
        evidence["tenant_match"] = True
        evidence["app_exact"] = True
        evidence["service_principal_found"] = True
        evidence["workspace_exact"] = True

        status, roles = list_role_assignments(workspace_id, token)
        if status != 200:
            raise ApplyError(f"role_assignments_status:{status}")

        current = target_assignments(roles, sp_object_id, app_id)
        current_roles = sorted({
            str(row.get("role") or "")
            for row in current
            if str(row.get("role") or "")
        })
        evidence["pre_assignment_count"] = len(current)
        evidence["pre_roles"] = current_roles

        if len(current) > 1:
            raise ApplyError("duplicate_target_assignments")

        if len(current) == 1:
            current_role = str(current[0].get("role") or "")
            if current_role == TARGET_ROLE:
                evidence["status"] = "already_present"
            elif current_role in {"Member", "Admin"}:
                raise ApplyError(f"higher_privilege_present:{current_role}")
            elif current_role == "Viewer":
                assignment_id = str(current[0].get("id") or "")
                if not assignment_id:
                    raise ApplyError("assignment_id_missing")
                mutation_status, _ = request_json(
                    "PATCH",
                    f"{FABRIC_ROOT}/workspaces/{workspace_id}/roleAssignments/{assignment_id}",
                    token,
                    {"role": TARGET_ROLE},
                )
                evidence["mutation_performed"] = True
                evidence["mutation_kind"] = "upgrade_viewer_to_contributor"
                evidence["mutation_status"] = mutation_status
                if mutation_status != 200:
                    raise ApplyError(f"patch_status:{mutation_status}")
            else:
                raise ApplyError(f"unexpected_existing_role:{current_role or 'empty'}")
        else:
            mutation_status, _ = request_json(
                "POST",
                f"{FABRIC_ROOT}/workspaces/{workspace_id}/roleAssignments",
                token,
                {
                    "principal": {
                        "id": sp_object_id,
                        "type": "ServicePrincipal",
                    },
                    "role": TARGET_ROLE,
                },
            )
            evidence["mutation_performed"] = True
            evidence["mutation_kind"] = "create_contributor"
            evidence["mutation_status"] = mutation_status
            if mutation_status != 201:
                raise ApplyError(f"post_status:{mutation_status}")

        verified: list[dict] = []
        verify_status = 0
        for delay in (0, 1, 2, 4, 8, 8):
            if delay:
                time.sleep(delay)
            verify_status, verify_roles = list_role_assignments(workspace_id, token)
            if verify_status != 200:
                continue
            verified = target_assignments(verify_roles, sp_object_id, app_id)
            verified_roles = sorted({
                str(row.get("role") or "")
                for row in verified
                if str(row.get("role") or "")
            })
            if len(verified) == 1 and verified_roles == [TARGET_ROLE]:
                break

        evidence["verification_assignment_count"] = len(verified)
        evidence["verification_roles"] = sorted({
            str(row.get("role") or "")
            for row in verified
            if str(row.get("role") or "")
        })
        evidence["postcondition_ok"] = (
            verify_status == 200
            and evidence["verification_assignment_count"] == 1
            and evidence["verification_roles"] == [TARGET_ROLE]
        )
        if not evidence["postcondition_ok"]:
            raise ApplyError(f"postcondition_failed:{verify_status}")

        if evidence["status"] != "already_present":
            evidence["status"] = "applied"
        return 0
    except (ApplyError, ProbeError, json.JSONDecodeError) as exc:
        evidence["reason"] = str(exc).splitlines()[0][:160]
        return 2
    except Exception as exc:
        evidence["reason"] = f"unexpected:{type(exc).__name__}"
        return 3
    finally:
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("FABRIC_HML_ROLE_ASSIGNMENT")
        for key in (
            "status",
            "target_role",
            "host_ok",
            "tenant_match",
            "app_exact",
            "service_principal_found",
            "workspace_exact",
            "pre_assignment_count",
            "pre_roles",
            "mutation_performed",
            "mutation_kind",
            "mutation_status",
            "verification_assignment_count",
            "verification_roles",
            "postcondition_ok",
            "production_touched",
            "secret_value_exposed",
            "identifiers_exposed",
        ):
            print(f"{key}={evidence.get(key)}")
        if evidence.get("reason"):
            print(f"reason={evidence['reason']}")


if __name__ == "__main__":
    sys.exit(main())
