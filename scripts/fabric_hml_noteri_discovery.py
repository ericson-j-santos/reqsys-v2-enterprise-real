#!/usr/bin/env python3
"""Descobre e provisiona apenas identificadores nao sensiveis do Fabric HML via Noteri."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

EXPECTED_HOST = "NOTERI"
DEFAULT_TENANT_ID = "6d09c88c-0617-490c-8329-305e577684bc"
DEFAULT_APP_NAME = "ReqSys ALM Pipeline"
DEFAULT_WORKSPACE_NAME = "ReqSys - Observabilidade"
DEFAULT_TARGET_REPO = "ericson-j-santos/painel-powerbi"
DEFAULT_TARGET_ENV = "homologacao"


class ProbeError(RuntimeError):
    pass


def _run(args: list[str], timeout: int = 45) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, shell=False)
    if proc.returncode != 0:
        raise ProbeError(f"command_failed:{Path(args[0]).name}:{proc.returncode}")
    return proc.stdout.strip()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _get_json(url: str, token: str) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def _gh_secret_names(repo: str, environment: str) -> set[str]:
    raw = _run(["gh", "secret", "list", "--env", environment, "--repo", repo, "--json", "name"])
    return {str(item.get("name") or "") for item in json.loads(raw or "[]")}


def _gh_variable_names(repo: str, environment: str) -> set[str]:
    raw = _run(["gh", "variable", "list", "--env", environment, "--repo", repo, "--json", "name"])
    return {str(item.get("name") or "") for item in json.loads(raw or "[]")}


def _set_variable(repo: str, environment: str, name: str, value: str) -> None:
    _run(["gh", "variable", "set", name, "--env", environment, "--repo", repo, "--body", value])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-file", required=True)
    parser.add_argument("--target-repo", default=DEFAULT_TARGET_REPO)
    parser.add_argument("--target-environment", default=DEFAULT_TARGET_ENV)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--app-name", default=DEFAULT_APP_NAME)
    parser.add_argument("--workspace-name", default=DEFAULT_WORKSPACE_NAME)
    parser.add_argument("--apply-nonsecret-vars", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

    evidence = {
        "schema": "fabric-hml-noteri-discovery/v1",
        "host_ok": False,
        "azure_cli_authenticated": False,
        "tenant_match": False,
        "github_target_access": False,
        "app_exact_count": 0,
        "workspace_exact_count": 0,
        "fabric_api_status": None,
        "target_secret_present": False,
        "target_variables_present": [],
        "variables_applied": False,
        "ready_for_secret_or_e2e": False,
        "secret_value_exposed": False,
        "identifiers_exposed": False,
    }
    output = Path(args.evidence_file)
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        evidence["host_ok"] = platform.node().strip().upper() == EXPECTED_HOST
        if not evidence["host_ok"]:
            raise ProbeError("unexpected_host")

        account = json.loads(_run(["az", "account", "show", "--output", "json"]))
        tenant = str(account.get("tenantId") or "")
        evidence["azure_cli_authenticated"] = bool(tenant)
        evidence["tenant_match"] = tenant.casefold() == args.tenant_id.casefold()
        if not evidence["tenant_match"]:
            raise ProbeError("azure_tenant_mismatch")

        _run(["gh", "repo", "view", args.target_repo, "--json", "nameWithOwner"])
        evidence["github_target_access"] = True

        apps = json.loads(_run(["az", "ad", "app", "list", "--display-name", args.app_name, "--output", "json"]))
        exact_apps = [row for row in apps if str(row.get("displayName") or "") == args.app_name]
        evidence["app_exact_count"] = len(exact_apps)

        token = _run([
            "az", "account", "get-access-token",
            "--resource", "https://api.fabric.microsoft.com",
            "--query", "accessToken", "-o", "tsv",
        ])
        status, payload = _get_json("https://api.fabric.microsoft.com/v1/workspaces", token)
        evidence["fabric_api_status"] = status
        workspaces = payload.get("value", []) if status == 200 else []
        exact_workspaces = [
            row for row in workspaces
            if str(row.get("displayName") or "") == args.workspace_name
        ]
        evidence["workspace_exact_count"] = len(exact_workspaces)

        secret_names = _gh_secret_names(args.target_repo, args.target_environment)
        variable_names = _gh_variable_names(args.target_repo, args.target_environment)
        evidence["target_secret_present"] = "FABRIC_CLIENT_SECRET" in secret_names
        evidence["target_variables_present"] = sorted(
            name for name in ("FABRIC_TENANT_ID", "FABRIC_CLIENT_ID", "FABRIC_WORKSPACE_ID")
            if name in variable_names
        )

        if args.apply_nonsecret_vars:
            if args.confirm != "APPLY-FABRIC-HML-NONSECRET-VARS":
                raise ProbeError("confirmation_required")
            if len(exact_apps) != 1:
                raise ProbeError("app_not_unique")
            if len(exact_workspaces) != 1:
                raise ProbeError("workspace_not_unique")

            app_id = str(exact_apps[0].get("appId") or "")
            workspace_id = str(exact_workspaces[0].get("id") or "")
            if not app_id or not workspace_id:
                raise ProbeError("identifier_missing")

            _set_variable(args.target_repo, args.target_environment, "FABRIC_TENANT_ID", args.tenant_id)
            _set_variable(args.target_repo, args.target_environment, "FABRIC_CLIENT_ID", app_id)
            _set_variable(args.target_repo, args.target_environment, "FABRIC_WORKSPACE_ID", workspace_id)
            evidence["variables_applied"] = True
            evidence["tenant_id_sha256"] = _digest(args.tenant_id)
            evidence["client_id_sha256"] = _digest(app_id)
            evidence["workspace_id_sha256"] = _digest(workspace_id)

            variable_names = _gh_variable_names(args.target_repo, args.target_environment)
            evidence["target_variables_present"] = sorted(
                name for name in ("FABRIC_TENANT_ID", "FABRIC_CLIENT_ID", "FABRIC_WORKSPACE_ID")
                if name in variable_names
            )

        evidence["ready_for_secret_or_e2e"] = (
            evidence["app_exact_count"] == 1
            and evidence["workspace_exact_count"] == 1
            and len(evidence["target_variables_present"]) == 3
        )
        evidence["status"] = "ok"
    except Exception as exc:
        evidence["status"] = "blocked"
        evidence["reason"] = str(exc).splitlines()[0][:160]
    finally:
        output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print("FABRIC_HML_NOTERI_DISCOVERY")
    for key in (
        "status", "host_ok", "azure_cli_authenticated", "tenant_match",
        "github_target_access", "app_exact_count", "workspace_exact_count",
        "fabric_api_status", "target_secret_present", "variables_applied",
        "ready_for_secret_or_e2e", "secret_value_exposed", "identifiers_exposed",
    ):
        print(f"{key}={evidence.get(key)}")
    if evidence.get("reason"):
        print(f"reason={evidence['reason']}")
    return 0 if evidence.get("status") == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
