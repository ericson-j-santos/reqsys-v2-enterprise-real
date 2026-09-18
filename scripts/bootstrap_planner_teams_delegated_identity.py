#!/usr/bin/env python3
"""Bootstrap idempotente da App Registration delegada do Planner→Teams DEV.

Executa sob a identidade mutadora do Credential Control Plane, com
Application.ReadWrite.OwnedBy temporariamente concedido por um operador
autorizado. Não cria client secret e não concede admin consent.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

CONFIRMATION = "CRIAR-IDENTIDADE-PLANNER-TEAMS-DEV"
DEFAULT_APP_NAME = "ReqSys Planner Teams Automation DEV"
DEFAULT_VAULT = "kv-reqsys-ccp"
DEFAULT_CLIENT_ID_SECRET = "reqsys-planner-teams-delegated-client-id-dev"
EXPECTED_AUDIENCE = "AzureADMyOrg"

POWER_PLATFORM_IDENTIFIERS = (
    "https://api.powerplatform.com",
    "https://api.powerplatform.com/",
)
FLOW_IDENTIFIERS = (
    "https://service.flow.microsoft.com",
    "https://service.flow.microsoft.com/",
)
POWER_PLATFORM_SCOPES = (
    "EnvironmentManagement.Environments.Read",
    "Connectivity.Connections.Read",
)
FLOW_SCOPES = ("Flows.Manage.All",)


class BootstrapError(RuntimeError):
    pass


def _cli() -> str:
    for candidate in ("az", "az.cmd", "az.exe"):
        if resolved := shutil.which(candidate):
            return resolved
    raise BootstrapError("azure_cli_ausente")


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run([_cli(), *args], text=True, capture_output=True, check=False, encoding="utf-8")
    if check and cp.returncode:
        detail = (cp.stderr or cp.stdout or "azure_cli_failed").strip()
        raise BootstrapError(detail[:1000])
    return cp


def _json(args: list[str]) -> Any:
    cp = _run([*args, "--output", "json"])
    try:
        return json.loads(cp.stdout or "null")
    except json.JSONDecodeError as exc:
        raise BootstrapError("azure_cli_json_invalido") from exc


def _tenant() -> str:
    value = (_run(["account", "show", "--query", "tenantId", "--output", "tsv"]).stdout or "").strip()
    if not value:
        raise BootstrapError("azure_session_ausente")
    return value


def _assert_vault(vault: str) -> None:
    cp = _run(
        ["keyvault", "secret", "list", "--vault-name", vault, "--maxresults", "1", "--output", "none", "--only-show-errors"],
        check=False,
    )
    if cp.returncode:
        raise BootstrapError("key_vault_unreachable")


def _find_app(display_name: str) -> dict[str, Any] | None:
    data = _json(["ad", "app", "list", "--display-name", display_name])
    if not isinstance(data, list):
        raise BootstrapError("app_inventory_invalido")
    exact = [item for item in data if isinstance(item, dict) and item.get("displayName") == display_name]
    if len(exact) > 1:
        raise BootstrapError("app_registration_ambigua")
    return exact[0] if exact else None


def _create_app(display_name: str) -> dict[str, Any]:
    data = _json(
        [
            "ad", "app", "create",
            "--display-name", display_name,
            "--sign-in-audience", EXPECTED_AUDIENCE,
            "--is-fallback-public-client", "true",
            "--query", "{id:id,appId:appId,displayName:displayName,signInAudience:signInAudience,isFallbackPublicClient:isFallbackPublicClient}",
        ]
    )
    if not isinstance(data, dict) or not data.get("id") or not data.get("appId"):
        raise BootstrapError("app_create_response_invalida")
    return data


def _app_details(app_id: str) -> dict[str, Any]:
    data = _json(
        [
            "ad", "app", "show", "--id", app_id,
            "--query", "{id:id,appId:appId,displayName:displayName,signInAudience:signInAudience,isFallbackPublicClient:isFallbackPublicClient,requiredResourceAccess:requiredResourceAccess}",
        ]
    )
    if not isinstance(data, dict):
        raise BootstrapError("app_details_invalidos")
    return data


def _ensure_public_client(object_id: str, details: dict[str, Any]) -> bool:
    if details.get("signInAudience") not in (None, "", EXPECTED_AUDIENCE):
        raise BootstrapError("app_sign_in_audience_incompativel")
    if details.get("isFallbackPublicClient") is True:
        return False
    body = json.dumps({"isFallbackPublicClient": True}, separators=(",", ":"))
    _run(
        [
            "rest", "--method", "PATCH",
            "--url", f"https://graph.microsoft.com/v1.0/applications/{object_id}",
            "--headers", "Content-Type=application/json",
            "--body", body,
            "--output", "none",
        ]
    )
    return True


def _ensure_service_principal(app_id: str) -> bool:
    cp = _run(["ad", "sp", "show", "--id", app_id, "--output", "none"], check=False)
    if cp.returncode == 0:
        return False
    _run(["ad", "sp", "create", "--id", app_id, "--output", "none"])
    return True


def _resource_service_principal(identifiers: tuple[str, ...], scopes: tuple[str, ...]) -> dict[str, Any]:
    for identifier in identifiers:
        data = _json(
            [
                "ad", "sp", "list",
                "--filter", f"servicePrincipalNames/any(x:x eq '{identifier}')",
                "--query", "[0].{appId:appId,oauth2PermissionScopes:oauth2PermissionScopes}",
            ]
        )
        if not isinstance(data, dict) or not data.get("appId"):
            continue
        available = {
            str(item.get("value")): str(item.get("id"))
            for item in data.get("oauth2PermissionScopes") or []
            if isinstance(item, dict) and item.get("isEnabled", True) and item.get("value") and item.get("id")
        }
        missing = [scope for scope in scopes if scope not in available]
        if missing:
            raise BootstrapError("delegated_scope_missing:" + ",".join(missing))
        return {"appId": str(data["appId"]), "scopes": {scope: available[scope] for scope in scopes}}
    raise BootstrapError("resource_service_principal_not_found")


def _merge_required_access(
    current: list[dict[str, Any]],
    resources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    by_resource: dict[str, dict[str, str]] = {}
    for item in current or []:
        if not isinstance(item, dict):
            continue
        resource_app_id = str(item.get("resourceAppId") or "")
        if not resource_app_id:
            continue
        bucket = by_resource.setdefault(resource_app_id, {})
        for access in item.get("resourceAccess") or []:
            if isinstance(access, dict) and access.get("id") and access.get("type"):
                bucket[str(access["id"])] = str(access["type"])

    changed = False
    for resource in resources:
        resource_app_id = str(resource["appId"])
        bucket = by_resource.setdefault(resource_app_id, {})
        for scope_id in resource["scopes"].values():
            if bucket.get(str(scope_id)) != "Scope":
                bucket[str(scope_id)] = "Scope"
                changed = True

    merged = [
        {
            "resourceAppId": resource_app_id,
            "resourceAccess": [
                {"id": access_id, "type": access_type}
                for access_id, access_type in sorted(access.items())
            ],
        }
        for resource_app_id, access in sorted(by_resource.items())
    ]
    return merged, changed


def _ensure_permissions(object_id: str, details: dict[str, Any]) -> bool:
    power = _resource_service_principal(POWER_PLATFORM_IDENTIFIERS, POWER_PLATFORM_SCOPES)
    flow = _resource_service_principal(FLOW_IDENTIFIERS, FLOW_SCOPES)
    merged, changed = _merge_required_access(details.get("requiredResourceAccess") or [], [power, flow])
    if not changed:
        return False
    body = json.dumps({"requiredResourceAccess": merged}, separators=(",", ":"))
    _run(
        [
            "rest", "--method", "PATCH",
            "--url", f"https://graph.microsoft.com/v1.0/applications/{object_id}",
            "--headers", "Content-Type=application/json",
            "--body", body,
            "--output", "none",
        ]
    )
    return True


def _store_client_id(vault: str, secret_name: str, app_id: str) -> None:
    _run(
        [
            "keyvault", "secret", "set",
            "--vault-name", vault,
            "--name", secret_name,
            "--value", app_id,
            "--content-type", "text/plain",
            "--tags",
            "credential_id=planner-teams-delegated-client-id-dev",
            "environment=dev",
            "component=planner-teams",
            "managed-by=reqsys",
            "--output", "none",
            "--only-show-errors",
        ]
    )


def _delete_app(object_id: str) -> None:
    _run(["ad", "app", "delete", "--id", object_id], check=False)


def bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise BootstrapError(f"confirmacao_invalida:{CONFIRMATION}")
    tenant = _tenant()
    if args.tenant_id and tenant.lower() != args.tenant_id.lower():
        raise BootstrapError("tenant_diverge")
    _assert_vault(args.vault_name)

    existing = _find_app(args.app_display_name)
    if args.dry_run:
        return {
            "schema_version": "1.0.0",
            "status": "dry_run",
            "environment": "dev",
            "app_display_name": args.app_display_name,
            "app_exists": existing is not None,
            "client_secret_created": False,
            "admin_consent_granted": False,
            "secret_value_exposed": False,
            "planned_actions": [
                "create_or_reuse_single_tenant_public_client",
                "configure_minimum_delegated_permissions",
                "store_nonsecret_client_id_in_key_vault",
            ],
        }

    created = False
    object_id = ""
    try:
        app = existing or _create_app(args.app_display_name)
        created = existing is None
        app_id = str(app.get("appId") or "")
        object_id = str(app.get("id") or "")
        if not app_id or not object_id:
            details = _app_details(app_id or object_id)
            app_id = str(details.get("appId") or "")
            object_id = str(details.get("id") or "")
        if not app_id or not object_id:
            raise BootstrapError("app_identifiers_missing")

        details = _app_details(app_id)
        public_client_changed = _ensure_public_client(object_id, details)
        details = _app_details(app_id)
        permissions_changed = _ensure_permissions(object_id, details)
        sp_created = _ensure_service_principal(app_id)

        verified = _app_details(app_id)
        if verified.get("signInAudience") != EXPECTED_AUDIENCE:
            raise BootstrapError("app_not_single_tenant_after_write")
        if verified.get("isFallbackPublicClient") is not True:
            raise BootstrapError("public_client_not_enabled_after_write")

        _store_client_id(args.vault_name, args.client_id_secret_name, app_id)

        return {
            "schema_version": "1.0.0",
            "status": "ready",
            "environment": "dev",
            "tenant_id": tenant,
            "app_display_name": args.app_display_name,
            "app_id": app_id,
            "created_app": created,
            "created_service_principal": sp_created,
            "public_client_changed": public_client_changed,
            "permissions_changed": permissions_changed,
            "delegated_permissions": [*POWER_PLATFORM_SCOPES, *FLOW_SCOPES],
            "client_id_secret_name": args.client_id_secret_name,
            "client_secret_created": False,
            "admin_consent_granted": False,
            "secret_value_exposed": False,
            "next_action": "Executar aceite DEV; a primeira autorização delegada poderá exigir consentimento/MFA humano.",
        }
    except Exception:
        if created and object_id:
            _delete_app(object_id)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--tenant-id", default="")
    parser.add_argument("--app-display-name", default=DEFAULT_APP_NAME)
    parser.add_argument("--vault-name", default=DEFAULT_VAULT)
    parser.add_argument("--client-id-secret-name", default=DEFAULT_CLIENT_ID_SECRET)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default="audit/planner-teams-delegated-identity-bootstrap.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = bootstrap(args)
        code = 0
    except BootstrapError as exc:
        result = {
            "schema_version": "1.0.0",
            "status": "blocked",
            "environment": "dev",
            "reason": str(exc),
            "client_secret_created": False,
            "admin_consent_granted": False,
            "secret_value_exposed": False,
        }
        code = 20
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
