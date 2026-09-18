#!/usr/bin/env python3
"""Ciclo administrativo temporário para materializar a identidade Planner→Teams DEV.

Requer sessões locais Microsoft Entra e GitHub já autenticadas. Concede somente
Application.ReadWrite.OwnedBy à identidade mutadora, dispara o workflow confiável
na main, valida a identidade/FIC e revoga a permissão em finally.

Nunca concede Application.ReadWrite.All e nunca recebe senha, MFA, token, client
secret ou refresh token por argumento.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"
OWNED_BY_APP_ROLE_ID = "18a4783c-866b-4cc7-a460-3d5e5662c884"
CONFIRMATION = "TEMP-OWNEDBY-PLANNER-TEAMS-DEV"
ISSUER = "https://token.actions.githubusercontent.com"
AUDIENCE = "api://AzureADTokenExchange"
DEFAULT_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_ENVIRONMENT = "reqsys-power-platform-dev"
DEFAULT_CREDENTIAL_NAME = "reqsys-planner-teams-acceptance-keyvault"
DEFAULT_VAULT = "kv-reqsys-ccp"
DEFAULT_CLIENT_ID_SECRET = "reqsys-planner-teams-delegated-client-id-dev"
WORKFLOW_FILE = "planner-teams-delegated-identity-bootstrap.yml"


class BootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class Context:
    tenant_id: str
    mutator_app_object_id: str
    mutator_service_principal_id: str
    graph_service_principal_id: str


def _tool(name: str) -> str:
    for candidate in (name, f"{name}.exe", f"{name}.cmd", f"{name}.bat"):
        if resolved := shutil.which(candidate):
            return resolved
    raise BootstrapError(f"ferramenta_obrigatoria_ausente:{name}")


def _run(tool: str, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [_tool(tool), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout or "erro_sem_detalhe").strip()
        raise BootstrapError(detail[:1200])
    return result


def _az_json(args: list[str]) -> Any:
    try:
        return json.loads(_run("az", args).stdout or "null")
    except json.JSONDecodeError as exc:
        raise BootstrapError("azure_cli_json_invalido") from exc


def _az_tsv(args: list[str]) -> str:
    return (_run("az", args).stdout or "").strip()


def _resolve_context(mutator_client_id: str, expected_tenant: str) -> Context:
    tenant = _az_tsv(["account", "show", "--query", "tenantId", "--output", "tsv"])
    if not tenant:
        raise BootstrapError("sessao_azure_ausente")
    if tenant.lower() != expected_tenant.lower():
        raise BootstrapError("tenant_ativo_diverge")
    app_id = _az_tsv(["ad", "app", "show", "--id", mutator_client_id, "--query", "id", "--output", "tsv"])
    sp_id = _az_tsv(["ad", "sp", "show", "--id", mutator_client_id, "--query", "id", "--output", "tsv"])
    graph_sp = _az_tsv(["ad", "sp", "show", "--id", GRAPH_APP_ID, "--query", "id", "--output", "tsv"])
    if not all((app_id, sp_id, graph_sp)):
        raise BootstrapError("contexto_mutador_incompleto")
    return Context(tenant, app_id, sp_id, graph_sp)


def _graph(method: str, url: str, *, body: dict[str, Any] | None = None) -> Any:
    args = ["rest", "--method", method, "--url", url, "--output", "json"]
    if body is not None:
        args += ["--headers", "Content-Type=application/json", "--body", json.dumps(body, separators=(",", ":"))]
    if method == "DELETE":
        _run("az", args)
        return None
    return _az_json(args)


def _owners(app_object_id: str) -> list[str]:
    payload = _graph("GET", f"https://graph.microsoft.com/v1.0/applications/{app_object_id}/owners?$select=id")
    values = payload.get("value", []) if isinstance(payload, dict) else []
    return [str(item.get("id")) for item in values if isinstance(item, dict) and item.get("id")]


def _assignments(sp_id: str) -> list[dict[str, Any]]:
    payload = _graph("GET", f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_id}/appRoleAssignments")
    values = payload.get("value", []) if isinstance(payload, dict) else []
    return [item for item in values if isinstance(item, dict)]


def _existing_ownedby_assignment(sp_id: str, graph_sp_id: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in _assignments(sp_id)
            if str(item.get("resourceId")) == graph_sp_id
            and str(item.get("appRoleId")) == OWNED_BY_APP_ROLE_ID
        ),
        None,
    )


def _grant_ownedby(sp_id: str, graph_sp_id: str) -> str:
    payload = _graph(
        "POST",
        f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_id}/appRoleAssignments",
        body={
            "principalId": sp_id,
            "resourceId": graph_sp_id,
            "appRoleId": OWNED_BY_APP_ROLE_ID,
        },
    )
    assignment_id = str(payload.get("id") or "") if isinstance(payload, dict) else ""
    if not assignment_id:
        raise BootstrapError("ownedby_assignment_id_ausente")
    return assignment_id


def _revoke_assignment(sp_id: str, assignment_id: str) -> None:
    _graph(
        "DELETE",
        f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_id}/appRoleAssignments/{assignment_id}",
    )


def _main_sha(repository: str) -> str:
    return (_run("gh", ["api", f"repos/{repository}/commits/main", "--jq", ".sha"]).stdout or "").strip()


def _dispatch_bootstrap_workflow(repository: str, expected_sha: str) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    _run("gh", ["workflow", "run", WORKFLOW_FILE, "--repo", repository, "--ref", "main"])
    run: dict[str, Any] | None = None
    for _ in range(24):
        time.sleep(5)
        raw = _run(
            "gh",
            [
                "run", "list",
                "--repo", repository,
                "--workflow", WORKFLOW_FILE,
                "--branch", "main",
                "--event", "workflow_dispatch",
                "--limit", "20",
                "--json", "databaseId,headSha,status,conclusion,createdAt,url",
            ],
        ).stdout or "[]"
        rows = json.loads(raw)
        run = next(
            (
                item
                for item in rows
                if item.get("headSha") == expected_sha
                and str(item.get("createdAt") or "") >= started
            ),
            None,
        )
        if run:
            break
    if not run:
        raise BootstrapError("bootstrap_run_nao_localizado_no_sha")
    run_id = int(run["databaseId"])
    _run("gh", ["run", "watch", str(run_id), "--repo", repository, "--exit-status"])
    raw = _run(
        "gh",
        ["run", "view", str(run_id), "--repo", repository, "--json", "databaseId,headSha,status,conclusion,url"],
    ).stdout or "{}"
    final = json.loads(raw)
    if final.get("headSha") != expected_sha or final.get("conclusion") != "success":
        raise BootstrapError("bootstrap_workflow_nao_verde_no_sha")
    return {
        "run_id": run_id,
        "head_sha": expected_sha,
        "conclusion": "success",
        "url": final.get("url"),
    }


def _verify_acceptance_fic(app_object_id: str, credential_name: str, subject: str) -> bool:
    payload = _graph(
        "GET",
        f"https://graph.microsoft.com/v1.0/applications/{app_object_id}/federatedIdentityCredentials",
    )
    values = payload.get("value", []) if isinstance(payload, dict) else []
    return any(
        isinstance(item, dict)
        and str(item.get("name") or "") == credential_name
        and str(item.get("issuer") or "") == ISSUER
        and str(item.get("subject") or "") == subject
        and item.get("audiences") == [AUDIENCE]
        for item in values
    )


def _dedicated_client_id(vault: str, secret_name: str) -> str:
    value = _az_tsv(
        [
            "keyvault", "secret", "show",
            "--vault-name", vault,
            "--name", secret_name,
            "--query", "value",
            "--output", "tsv",
            "--only-show-errors",
        ]
    )
    if not value:
        raise BootstrapError("dedicated_client_id_ausente_no_key_vault")
    return value


def _verify_dedicated_app(client_id: str) -> bool:
    payload = _az_json(
        [
            "ad", "app", "show",
            "--id", client_id,
            "--query", "{appId:appId,signInAudience:signInAudience,isFallbackPublicClient:isFallbackPublicClient}",
        ]
    )
    return bool(
        isinstance(payload, dict)
        and str(payload.get("appId") or "").lower() == client_id.lower()
        and payload.get("signInAudience") == "AzureADMyOrg"
        and payload.get("isFallbackPublicClient") is True
    )


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise BootstrapError(f"confirmacao_invalida:{CONFIRMATION}")

    ctx = _resolve_context(args.mutator_client_id, args.tenant_id)
    if ctx.mutator_service_principal_id not in _owners(ctx.mutator_app_object_id):
        return {
            "status": "blocked",
            "reason": "MUTATOR_NOT_OWNER",
            "requires_human_decision": "assign_mutator_service_principal_as_owner",
            "application_readwrite_all_granted": False,
            "secret_value_exposed": False,
        }
    if _existing_ownedby_assignment(ctx.mutator_service_principal_id, ctx.graph_service_principal_id):
        return {
            "status": "blocked",
            "reason": "OWNEDBY_ALREADY_PRESENT",
            "requires_human_decision": "preexisting_permission_must_not_be_revoked_implicitly",
            "application_readwrite_all_granted": False,
            "secret_value_exposed": False,
        }
    if args.dry_run:
        return {
            "status": "dry_run",
            "environment": "dev",
            "planned_action": "grant_ownedby_dispatch_identity_bootstrap_revoke_ownedby",
            "application_readwrite_all_granted": False,
            "secret_value_exposed": False,
        }

    assignment_id = ""
    workflow_evidence: dict[str, Any] | None = None
    subject = f"repo:{args.repository}:environment:{args.environment}"
    try:
        assignment_id = _grant_ownedby(ctx.mutator_service_principal_id, ctx.graph_service_principal_id)
        if not _existing_ownedby_assignment(ctx.mutator_service_principal_id, ctx.graph_service_principal_id):
            raise BootstrapError("ownedby_temporario_nao_comprovado")

        main_sha = _main_sha(args.repository)
        if not main_sha:
            raise BootstrapError("main_sha_ausente")
        workflow_evidence = _dispatch_bootstrap_workflow(args.repository, main_sha)

        if not _verify_acceptance_fic(ctx.mutator_app_object_id, args.credential_name, subject):
            raise BootstrapError("acceptance_fic_nao_comprovada")
        dedicated_client_id = _dedicated_client_id(args.vault_name, args.client_id_secret_name)
        if not _verify_dedicated_app(dedicated_client_id):
            raise BootstrapError("dedicated_app_nao_comprovada")
    finally:
        if assignment_id:
            _revoke_assignment(ctx.mutator_service_principal_id, assignment_id)

    if _existing_ownedby_assignment(ctx.mutator_service_principal_id, ctx.graph_service_principal_id):
        raise BootstrapError("ownedby_revogacao_nao_comprovada")

    return {
        "status": "ready",
        "environment": "dev",
        "subject": subject,
        "credential_name": args.credential_name,
        "ownedby_temporarily_granted": True,
        "ownedby_revoked": True,
        "application_readwrite_all_granted": False,
        "admin_consent_granted": False,
        "client_secret_created": False,
        "secret_value_exposed": False,
        "workflow": workflow_evidence,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap administrativo temporário Planner Teams DEV")
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--mutator-client-id", required=True)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--credential-name", default=DEFAULT_CREDENTIAL_NAME)
    parser.add_argument("--vault-name", default=DEFAULT_VAULT)
    parser.add_argument("--client-id-secret-name", default=DEFAULT_CLIENT_ID_SECRET)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        result = execute(parse_args(argv))
    except BootstrapError as exc:
        result = {
            "status": "blocked",
            "reason": str(exc),
            "environment": "dev",
            "application_readwrite_all_granted": False,
            "admin_consent_granted": False,
            "client_secret_created": False,
            "secret_value_exposed": False,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 4
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"ready", "dry_run"} else 5


if __name__ == "__main__":
    raise SystemExit(main())
