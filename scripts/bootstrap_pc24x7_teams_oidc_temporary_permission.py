#!/usr/bin/env python3
"""Automação governada do ciclo temporário Application.ReadWrite.OwnedBy.

Requer uma sessão Microsoft Entra administrativa já autenticada no Azure CLI.
O fluxo é fail-closed e opera somente em DEV:
1. valida tenant e App Registration mutadora;
2. comprova que o service principal chamador é owner da aplicação alvo;
3. concede temporariamente Application.ReadWrite.OwnedBy ao service principal;
4. cria/revalida a FIC do GitHub Environment development;
5. revoga a appRoleAssignment criada nesta execução;
6. comprova a revogação por releitura independente.

A automação NUNCA promove automaticamente para Application.ReadWrite.All.
Se ownership não estiver comprovado, retorna requires_human_decision.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"
OWNED_BY_APP_ROLE_ID = "18a4783c-866b-4cc7-a460-3d5e5662c884"
CONFIRMATION = "TEMP-OWNEDBY-PC24X7-TEAMS-DEV"
ISSUER = "https://token.actions.githubusercontent.com"
AUDIENCE = "api://AzureADTokenExchange"
DEFAULT_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_ENVIRONMENT = "development"
DEFAULT_CREDENTIAL_NAME = "reqsys-pc24x7-teams-development"


class BootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class Context:
    tenant_id: str
    mutator_app_object_id: str
    mutator_service_principal_id: str
    graph_service_principal_id: str


def _cli() -> str:
    for candidate in ("az", "az.cmd", "az.bat"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise BootstrapError("Azure CLI não encontrado.")


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    resolved = [_cli(), *args[1:]] if args and args[0] == "az" else args
    result = subprocess.run(resolved, check=False, capture_output=True, text=True, encoding="utf-8")
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "erro sem detalhe").strip()
        raise BootstrapError(detail[:1200])
    return result


def _json(args: list[str]) -> Any:
    result = _run(args)
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise BootstrapError("Microsoft Graph/Azure CLI retornou JSON inválido.") from exc


def _tsv(args: list[str]) -> str:
    return (_run(args).stdout or "").strip()


def _active_tenant() -> str:
    tenant = _tsv(["az", "account", "show", "--query", "tenantId", "--output", "tsv"])
    if not tenant:
        raise BootstrapError("Sessão Azure ausente ou inválida.")
    return tenant


def _resolve_context(mutator_client_id: str, expected_tenant: str) -> Context:
    tenant = _active_tenant()
    if expected_tenant and tenant.lower() != expected_tenant.lower():
        raise BootstrapError("Tenant ativo diverge do tenant esperado.")
    app_object_id = _tsv(["az", "ad", "app", "show", "--id", mutator_client_id, "--query", "id", "--output", "tsv"])
    sp_object_id = _tsv(["az", "ad", "sp", "show", "--id", mutator_client_id, "--query", "id", "--output", "tsv"])
    graph_sp_id = _tsv(["az", "ad", "sp", "show", "--id", GRAPH_APP_ID, "--query", "id", "--output", "tsv"])
    if not all((app_object_id, sp_object_id, graph_sp_id)):
        raise BootstrapError("Não foi possível resolver aplicação mutadora/service principals.")
    return Context(tenant, app_object_id, sp_object_id, graph_sp_id)


def _owners(app_object_id: str) -> list[str]:
    url = f"https://graph.microsoft.com/v1.0/applications/{app_object_id}/owners?$select=id"
    payload = _json(["az", "rest", "--method", "GET", "--url", url, "--output", "json"])
    values = payload.get("value", []) if isinstance(payload, dict) else []
    return [str(item.get("id")) for item in values if isinstance(item, dict) and item.get("id")]


def _assignments(sp_id: str) -> list[dict[str, Any]]:
    url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_id}/appRoleAssignments"
    payload = _json(["az", "rest", "--method", "GET", "--url", url, "--output", "json"])
    values = payload.get("value", []) if isinstance(payload, dict) else []
    return [item for item in values if isinstance(item, dict)]


def _existing_ownedby_assignment(sp_id: str, graph_sp_id: str) -> dict[str, Any] | None:
    for item in _assignments(sp_id):
        if str(item.get("resourceId")) == graph_sp_id and str(item.get("appRoleId")) == OWNED_BY_APP_ROLE_ID:
            return item
    return None


def _grant_ownedby(sp_id: str, graph_sp_id: str) -> str:
    url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_id}/appRoleAssignments"
    body = json.dumps({"principalId": sp_id, "resourceId": graph_sp_id, "appRoleId": OWNED_BY_APP_ROLE_ID}, separators=(",", ":"))
    result = _json(["az", "rest", "--method", "POST", "--url", url, "--headers", "Content-Type=application/json", "--body", body, "--output", "json"])
    assignment_id = str(result.get("id") or "") if isinstance(result, dict) else ""
    if not assignment_id:
        raise BootstrapError("Concessão OwnedBy não retornou appRoleAssignment id.")
    return assignment_id


def _revoke_assignment(sp_id: str, assignment_id: str) -> None:
    url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_id}/appRoleAssignments/{assignment_id}"
    _run(["az", "rest", "--method", "DELETE", "--url", url, "--output", "none"])


def _fic_url(app_object_id: str) -> str:
    return f"https://graph.microsoft.com/v1.0/applications/{app_object_id}/federatedIdentityCredentials"


def _subject(repository: str, environment: str) -> str:
    return f"repo:{repository}:environment:{environment}"


def _list_fics(app_object_id: str) -> list[dict[str, Any]]:
    payload = _json(["az", "rest", "--method", "GET", "--url", _fic_url(app_object_id), "--output", "json"])
    values = payload.get("value", []) if isinstance(payload, dict) else []
    return [item for item in values if isinstance(item, dict)]


def _fic_exact(item: dict[str, Any], name: str, subject: str) -> bool:
    return (
        str(item.get("name") or "") == name
        and str(item.get("issuer") or "") == ISSUER
        and str(item.get("subject") or "") == subject
        and item.get("audiences") == [AUDIENCE]
    )


def _ensure_fic(app_object_id: str, name: str, subject: str) -> bool:
    current = _list_fics(app_object_id)
    for item in current:
        if _fic_exact(item, name, subject):
            return False
        if str(item.get("name") or "") == name or str(item.get("subject") or "") == subject:
            raise BootstrapError("FIC conflitante encontrada; nenhuma alteração adicional foi feita.")
    body = json.dumps({
        "name": name,
        "issuer": ISSUER,
        "subject": subject,
        "description": "ReqSys PC24x7 Teams DEV temporary OwnedBy bootstrap",
        "audiences": [AUDIENCE],
    }, separators=(",", ":"))
    _run(["az", "rest", "--method", "POST", "--url", _fic_url(app_object_id), "--headers", "Content-Type=application/json", "--body", body, "--output", "none"])
    if not any(_fic_exact(item, name, subject) for item in _list_fics(app_object_id)):
        raise BootstrapError("Releitura não comprovou a FIC esperada.")
    return True


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise BootstrapError(f"Confirmação inválida. Use --confirm {CONFIRMATION}")
    ctx = _resolve_context(args.mutator_client_id, args.tenant_id)
    if ctx.mutator_service_principal_id not in _owners(ctx.mutator_app_object_id):
        return {
            "status": "blocked",
            "reason": "MUTATOR_NOT_OWNER",
            "requires_human_decision": "owner_assignment_or_explicit_Application.ReadWrite.All_decision",
            "environment": "dev",
            "application_readwrite_all_granted": False,
            "secret_value_exposed": False,
        }

    previous = _existing_ownedby_assignment(ctx.mutator_service_principal_id, ctx.graph_service_principal_id)
    if previous:
        return {
            "status": "blocked",
            "reason": "OWNEDBY_ALREADY_PRESENT",
            "requires_human_decision": "preexisting_permission_must_not_be_revoked_implicitly",
            "environment": "dev",
            "application_readwrite_all_granted": False,
            "secret_value_exposed": False,
        }

    assignment_id = ""
    fic_created = False
    subject = _subject(args.repository, args.environment)
    try:
        assignment_id = _grant_ownedby(ctx.mutator_service_principal_id, ctx.graph_service_principal_id)
        if not _existing_ownedby_assignment(ctx.mutator_service_principal_id, ctx.graph_service_principal_id):
            raise BootstrapError("Releitura não comprovou Application.ReadWrite.OwnedBy.")
        fic_created = _ensure_fic(ctx.mutator_app_object_id, args.credential_name, subject)
    finally:
        if assignment_id:
            _revoke_assignment(ctx.mutator_service_principal_id, assignment_id)

    if _existing_ownedby_assignment(ctx.mutator_service_principal_id, ctx.graph_service_principal_id):
        raise BootstrapError("Revogação temporária não foi comprovada; intervenção humana necessária.")

    return {
        "status": "ready",
        "environment": "dev",
        "subject": subject,
        "credential_name": args.credential_name,
        "fic_created": fic_created,
        "ownedby_temporarily_granted": True,
        "ownedby_revoked": True,
        "application_readwrite_all_granted": False,
        "rbac_changed": False,
        "secret_value_exposed": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automação temporária OwnedBy para FIC PC24x7 Teams DEV")
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--mutator-client-id", required=True)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--credential-name", default=DEFAULT_CREDENTIAL_NAME)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        result = execute(parse_args(argv))
    except BootstrapError as exc:
        print(json.dumps({
            "status": "blocked",
            "reason": str(exc),
            "environment": "dev",
            "application_readwrite_all_granted": False,
            "secret_value_exposed": False,
        }, ensure_ascii=False, sort_keys=True))
        return 4
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "ready" else 5


if __name__ == "__main__":
    raise SystemExit(main())
