#!/usr/bin/env python3
"""Bootstrap idempotente da credencial federada OIDC do PC24x7 Teams em DEV.

Este script deve ser executado somente por uma conta Microsoft Entra autorizada.
Ele cria, quando ausente, uma única Federated Identity Credential (FIC) para o
subject do GitHub Environment ``development``. Não cria App Registration, não
altera RBAC, não lê/grava segredos e não toca TEST/PROD.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from typing import Any


CONFIRMATION = "CRIAR-FIC-PC24X7-TEAMS-DEV"
DEFAULT_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_ENVIRONMENT = "development"
DEFAULT_CREDENTIAL_NAME = "reqsys-pc24x7-teams-development"
ISSUER = "https://token.actions.githubusercontent.com"
AUDIENCE = "api://AzureADTokenExchange"


class BootstrapError(RuntimeError):
    pass


def _cli() -> str:
    for candidate in ("az", "az.cmd", "az.bat"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise BootstrapError("Azure CLI não encontrado. Execute em host governado com Azure CLI disponível.")


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    resolved = [_cli(), *args[1:]] if args and args[0] == "az" else args
    result = subprocess.run(
        resolved,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "erro sem detalhe").strip()
        raise BootstrapError(detail[:1200])
    return result


def _account_tenant() -> str:
    result = _run(["az", "account", "show", "--query", "tenantId", "--output", "tsv"])
    tenant = (result.stdout or "").strip()
    if not tenant:
        raise BootstrapError("Sessão Azure inválida. Execute 'az login' no tenant correto.")
    return tenant


def _app_object_id(client_id: str) -> str:
    result = _run(["az", "ad", "app", "show", "--id", client_id, "--query", "id", "--output", "tsv"])
    object_id = (result.stdout or "").strip()
    if not object_id:
        raise BootstrapError("A App Registration da identidade mutadora não foi localizada.")
    return object_id


def _list_credentials(object_id: str) -> list[dict[str, Any]]:
    url = (
        "https://graph.microsoft.com/v1.0/applications/"
        f"{object_id}/federatedIdentityCredentials?$select=name,issuer,subject,audiences"
    )
    result = _run(["az", "rest", "--method", "GET", "--url", url, "--output", "json"])
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise BootstrapError("Microsoft Graph retornou JSON inválido ao consultar FICs.") from exc
    values = payload.get("value", []) if isinstance(payload, dict) else []
    if not isinstance(values, list):
        raise BootstrapError("Resposta inesperada do Microsoft Graph ao consultar FICs.")
    return [item for item in values if isinstance(item, dict)]


def _expected_subject(repository: str, environment: str) -> str:
    return f"repo:{repository}:environment:{environment}"


def _is_exact(item: dict[str, Any], *, name: str, subject: str) -> bool:
    audiences = item.get("audiences")
    return (
        str(item.get("name") or "") == name
        and str(item.get("issuer") or "") == ISSUER
        and str(item.get("subject") or "") == subject
        and isinstance(audiences, list)
        and audiences == [AUDIENCE]
    )


def _validate_no_conflict(credentials: list[dict[str, Any]], *, name: str, subject: str) -> None:
    for item in credentials:
        item_name = str(item.get("name") or "")
        item_subject = str(item.get("subject") or "")
        if item_name == name and not _is_exact(item, name=name, subject=subject):
            raise BootstrapError("Já existe FIC com o nome esperado, mas contrato diferente. Nenhuma alteração foi feita.")
        if item_subject == subject and not _is_exact(item, name=name, subject=subject):
            raise BootstrapError("Já existe FIC para o subject DEV, mas contrato diferente. Nenhuma alteração foi feita.")


def bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise BootstrapError(f"Confirmação inválida. Use --confirm {CONFIRMATION}")

    tenant = _account_tenant()
    if args.tenant_id and tenant.lower() != args.tenant_id.lower():
        raise BootstrapError("Tenant Azure ativo difere do tenant esperado. Nenhuma alteração foi feita.")

    subject = _expected_subject(args.repository, args.environment)
    object_id = _app_object_id(args.mutator_client_id)
    current = _list_credentials(object_id)

    for item in current:
        if _is_exact(item, name=args.credential_name, subject=subject):
            return {
                "schema_version": "1.0.0",
                "status": "ready",
                "environment": "dev",
                "credential_name": args.credential_name,
                "subject": subject,
                "created": False,
                "rbac_changed": False,
                "secret_value_exposed": False,
            }

    _validate_no_conflict(current, name=args.credential_name, subject=subject)

    if args.dry_run:
        return {
            "schema_version": "1.0.0",
            "status": "dry_run",
            "environment": "dev",
            "credential_name": args.credential_name,
            "subject": subject,
            "planned_action": "create_federated_identity_credential",
            "rbac_changed": False,
            "secret_value_exposed": False,
        }

    body = json.dumps(
        {
            "name": args.credential_name,
            "issuer": ISSUER,
            "subject": subject,
            "description": "ReqSys PC24x7 Teams bootstrap DEV; GitHub Environment development",
            "audiences": [AUDIENCE],
        },
        separators=(",", ":"),
    )
    url = f"https://graph.microsoft.com/v1.0/applications/{object_id}/federatedIdentityCredentials"
    _run(
        [
            "az",
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
        ]
    )

    after = _list_credentials(object_id)
    if not any(_is_exact(item, name=args.credential_name, subject=subject) for item in after):
        raise BootstrapError("FIC foi solicitada, mas a releitura não comprovou o contrato esperado.")

    return {
        "schema_version": "1.0.0",
        "status": "ready",
        "environment": "dev",
        "credential_name": args.credential_name,
        "subject": subject,
        "created": True,
        "rbac_changed": False,
        "secret_value_exposed": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap da FIC OIDC do PC24x7 Teams DEV")
    parser.add_argument("--confirm", required=True, help=f"confirmação literal: {CONFIRMATION}")
    parser.add_argument("--tenant-id", default="", help="tenant esperado; bloqueia execução em tenant diferente")
    parser.add_argument("--mutator-client-id", required=True, help="client ID da identidade mutadora já existente")
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--credential-name", default=DEFAULT_CREDENTIAL_NAME)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = bootstrap(args)
    except BootstrapError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "environment": "dev",
                    "rbac_changed": False,
                    "secret_value_exposed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 4
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
