#!/usr/bin/env python3
"""Bootstrap isolado do segredo Fabric HML sem expor o valor."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

EXPECTED_HOST = "NOTERI"
TENANT_ID = "6d09c88c-0617-490c-8329-305e577684bc"
APP_NAME = "ReqSys ALM Pipeline"
WORKSPACE_NAME = "ReqSys - Observabilidade"
TARGET_REPO = "ericson-j-santos/painel-powerbi"
TARGET_ENV = "homologacao"
TARGET_SECRET = "FABRIC_CLIENT_SECRET"


class BootstrapError(RuntimeError):
    pass


def run(args: list[str], *, timeout: int = 60) -> str:
    proc = subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, shell=False
    )
    if proc.returncode != 0:
        raise BootstrapError(f"command_failed:{Path(args[0]).name}:{proc.returncode}")
    return proc.stdout.strip()


def run_stdin(args: list[str], value: str, *, timeout: int = 60) -> None:
    proc = subprocess.run(
        args,
        input=value,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    if proc.returncode != 0:
        raise BootstrapError(f"command_failed:{Path(args[0]).name}:{proc.returncode}")


def find_az() -> str:
    for candidate in (
        shutil.which("az"),
        r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
    ):
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise BootstrapError("azure_cli_missing")


def exact_app(az: str) -> tuple[str, str]:
    account = json.loads(run([az, "account", "show", "--output", "json"]))
    tenant = str(account.get("tenantId") or "")
    if tenant.casefold() != TENANT_ID.casefold():
        raise BootstrapError("tenant_mismatch")

    apps = json.loads(
        run([az, "ad", "app", "list", "--display-name", APP_NAME, "--output", "json"])
    )
    exact = [row for row in apps if str(row.get("displayName") or "") == APP_NAME]
    if len(exact) != 1:
        raise BootstrapError(f"app_exact_count:{len(exact)}")
    app_id = str(exact[0].get("appId") or "")
    object_id = str(exact[0].get("id") or "")
    if not app_id or not object_id:
        raise BootstrapError("app_identifier_missing")
    return app_id, object_id


def user_fabric_token(az: str) -> str:
    token = run([
        az,
        "account",
        "get-access-token",
        "--resource",
        "https://api.fabric.microsoft.com",
        "--query",
        "accessToken",
        "-o",
        "tsv",
    ])
    if not token:
        raise BootstrapError("fabric_user_token_missing")
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


def exact_workspace_id(user_token: str) -> str:
    status, payload = get_json(
        "https://api.fabric.microsoft.com/v1/workspaces", user_token
    )
    if status != 200:
        raise BootstrapError(f"fabric_user_status:{status}")
    exact = [
        row
        for row in payload.get("value", [])
        if str(row.get("displayName") or "") == WORKSPACE_NAME
    ]
    if len(exact) != 1:
        raise BootstrapError(f"workspace_exact_count:{len(exact)}")
    workspace_id = str(exact[0].get("id") or "")
    if not workspace_id:
        raise BootstrapError("workspace_id_missing")
    return workspace_id


def gh_names(gh: str, kind: str) -> set[str]:
    raw = run([
        gh, kind, "list",
        "--env", TARGET_ENV,
        "--repo", TARGET_REPO,
        "--json", "name",
    ])
    return {str(row.get("name") or "") for row in json.loads(raw or "[]")}


def set_variable(gh: str, name: str, value: str) -> None:
    run([
        gh, "variable", "set", name,
        "--env", TARGET_ENV,
        "--repo", TARGET_REPO,
        "--body", value,
    ])


def credential_metadata(az: str, app_id: str) -> list[dict]:
    return json.loads(
        run([az, "ad", "app", "credential", "list", "--id", app_id, "-o", "json"])
        or "[]"
    )


def create_credential(az: str, app_id: str, display_name: str) -> tuple[str, str]:
    raw = run([
        az,
        "ad",
        "app",
        "credential",
        "reset",
        "--id",
        app_id,
        "--append",
        "--years",
        "1",
        "--display-name",
        display_name,
        "--output",
        "json",
    ])
    payload = json.loads(raw)
    password = str(payload.get("password") or "")
    if not password:
        raise BootstrapError("credential_password_missing")

    matches = [
        row
        for row in credential_metadata(az, app_id)
        if str(row.get("displayName") or "") == display_name
    ]
    if len(matches) != 1:
        raise BootstrapError(f"created_credential_match_count:{len(matches)}")
    key_id = str(matches[0].get("keyId") or "")
    if not key_id:
        raise BootstrapError("created_credential_key_id_missing")
    return password, key_id


def delete_credential(az: str, app_id: str, key_id: str) -> None:
    run([
        az,
        "ad",
        "app",
        "credential",
        "delete",
        "--id",
        app_id,
        "--key-id",
        key_id,
    ])


def validate_client_credentials(
    *, client_id: str, secret: str, workspace_id: str
) -> tuple[bool, int | None, bool]:
    body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": secret,
        "grant_type": "client_credentials",
        "scope": "https://api.fabric.microsoft.com/.default",
    }).encode("utf-8")
    request = urllib.request.Request(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            access_token = json.loads(resp.read().decode("utf-8")).get("access_token", "")
    except urllib.error.HTTPError as exc:
        return False, exc.code, False
    if not access_token:
        return False, None, False

    status, payload = get_json(
        "https://api.fabric.microsoft.com/v1/workspaces", str(access_token)
    )
    visible = status == 200 and any(
        str(row.get("id") or "") == workspace_id for row in payload.get("value", [])
    )
    return True, status, visible


def main() -> int:
    evidence_path = Path(
        os.environ.get(
            "EVIDENCE_FILE",
            "artifacts/fabric-hml-secret-bootstrap/evidence.json",
        )
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema": "fabric-hml-secret-bootstrap/v1",
        "status": "blocked",
        "host_ok": False,
        "tenant_match": False,
        "app_exact_count": 0,
        "workspace_exact_count": 0,
        "target_variables_present": [],
        "target_secret_present_before": False,
        "target_secret_present_after": False,
        "credential_created": False,
        "credential_rollback": False,
        "client_credentials_token_obtained": False,
        "fabric_api_status": None,
        "target_workspace_visible_to_app": False,
        "e2e_enabled": False,
        "secret_value_exposed": False,
        "identifiers_exposed": False,
    }

    az = ""
    gh = ""
    app_id = ""
    workspace_id = ""
    new_secret = ""
    new_key_id = ""

    try:
        evidence["host_ok"] = platform.node().strip().upper() == EXPECTED_HOST
        if not evidence["host_ok"]:
            raise BootstrapError("unexpected_host")

        az = find_az()
        gh = str(shutil.which("gh") or "")
        if not gh:
            raise BootstrapError("gh_cli_missing")
        run([gh, "repo", "view", TARGET_REPO, "--json", "nameWithOwner"])

        app_id, _ = exact_app(az)
        evidence["tenant_match"] = True
        evidence["app_exact_count"] = 1

        workspace_id = exact_workspace_id(user_fabric_token(az))
        evidence["workspace_exact_count"] = 1

        # Reaplica os identificadores de forma idempotente, sem imprimi-los.
        set_variable(gh, "FABRIC_TENANT_ID", TENANT_ID)
        set_variable(gh, "FABRIC_CLIENT_ID", app_id)
        set_variable(gh, "FABRIC_WORKSPACE_ID", workspace_id)

        variables = gh_names(gh, "variable")
        evidence["target_variables_present"] = sorted(
            name
            for name in ("FABRIC_TENANT_ID", "FABRIC_CLIENT_ID", "FABRIC_WORKSPACE_ID")
            if name in variables
        )
        if len(evidence["target_variables_present"]) != 3:
            raise BootstrapError("target_variables_incomplete")

        secrets_before = gh_names(gh, "secret")
        evidence["target_secret_present_before"] = TARGET_SECRET in secrets_before

        if evidence["target_secret_present_before"]:
            evidence["target_secret_present_after"] = True
            set_variable(gh, "FABRIC_HML_E2E_ENABLED", "true")
            evidence["e2e_enabled"] = (
                "FABRIC_HML_E2E_ENABLED" in gh_names(gh, "variable")
            )
            evidence["status"] = "secret_present_e2e_enabled"
            return 0

        credential_name = (
            "painel-powerbi-hml-"
            + str(os.environ.get("GITHUB_RUN_ID") or "manual")
        )
        new_secret, new_key_id = create_credential(az, app_id, credential_name)
        evidence["credential_created"] = True

        # O segredo segue somente por stdin; nunca entra em argv, arquivo ou stdout.
        try:
            run_stdin([
                gh,
                "secret",
                "set",
                TARGET_SECRET,
                "--env",
                TARGET_ENV,
                "--repo",
                TARGET_REPO,
            ], new_secret)
        except Exception:
            delete_credential(az, app_id, new_key_id)
            evidence["credential_rollback"] = True
            raise BootstrapError("github_secret_write_failed_rolled_back")

        secrets_after = gh_names(gh, "secret")
        evidence["target_secret_present_after"] = TARGET_SECRET in secrets_after
        if not evidence["target_secret_present_after"]:
            delete_credential(az, app_id, new_key_id)
            evidence["credential_rollback"] = True
            raise BootstrapError("github_secret_not_observed_rolled_back")

        token_ok, fabric_status, workspace_visible = validate_client_credentials(
            client_id=app_id,
            secret=new_secret,
            workspace_id=workspace_id,
        )
        evidence["client_credentials_token_obtained"] = token_ok
        evidence["fabric_api_status"] = fabric_status
        evidence["target_workspace_visible_to_app"] = workspace_visible

        if token_ok and fabric_status == 200 and workspace_visible:
            set_variable(gh, "FABRIC_HML_E2E_ENABLED", "true")
            evidence["e2e_enabled"] = (
                "FABRIC_HML_E2E_ENABLED" in gh_names(gh, "variable")
            )

        evidence["status"] = (
            "ready_for_e2e"
            if evidence["e2e_enabled"]
            else "secret_provisioned_access_pending"
        )
        return 0
    except Exception as exc:
        evidence["reason"] = str(exc).splitlines()[0][:160]
        return 2
    finally:
        # Evita uso acidental posterior do valor; o GC é apenas melhor esforço.
        new_secret = ""
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("FABRIC_HML_SECRET_BOOTSTRAP")
        for key in (
            "status",
            "host_ok",
            "tenant_match",
            "app_exact_count",
            "workspace_exact_count",
            "target_secret_present_before",
            "target_secret_present_after",
            "credential_created",
            "credential_rollback",
            "client_credentials_token_obtained",
            "fabric_api_status",
            "target_workspace_visible_to_app",
            "e2e_enabled",
            "secret_value_exposed",
            "identifiers_exposed",
        ):
            print(f"{key}={evidence.get(key)}")
        if evidence.get("reason"):
            print(f"reason={evidence['reason']}")


if __name__ == "__main__":
    sys.exit(main())
