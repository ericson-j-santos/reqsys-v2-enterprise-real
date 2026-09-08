#!/usr/bin/env python3
"""Bootstrap administrativo único da identidade do Azure Bot DEV.

O script deve ser executado por uma conta Microsoft Entra autorizada a criar/gerir
App Registrations e a gravar o segredo dedicado no Azure Key Vault. O valor do
segredo nunca é impresso, salvo em arquivo ou retornado na evidência.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CONFIRMATION = "CRIAR-IDENTIDADE-TEAMS-BOT-DEV"
DEFAULT_APP_NAME = "ReqSys Teams Bot DEV"
DEFAULT_VAULT = "kv-reqsys-ccp"
DEFAULT_SECRET_NAME = "reqsys-teams-bot-dev-secret"


class BootstrapError(RuntimeError):
    pass


def _run(args: list[str], *, check: bool = True, sensitive: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode != 0:
        if sensitive:
            raise BootstrapError("Falha em operação sensível; detalhes foram suprimidos para não expor credenciais.")
        detail = (result.stderr or result.stdout or "erro sem detalhe").strip()
        raise BootstrapError(detail[:1200])
    return result


def _json(args: list[str]) -> Any:
    result = _run([*args, "--output", "json"])
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise BootstrapError("Azure CLI retornou JSON inválido.") from exc


def _account() -> dict[str, Any]:
    data = _json(["az", "account", "show"])
    if not isinstance(data, dict) or not data.get("tenantId"):
        raise BootstrapError("Sessão Azure inválida. Execute 'az login' com a conta administrativa correta.")
    return data


def _find_app(display_name: str) -> tuple[dict[str, Any] | None, int]:
    apps = _json(["az", "ad", "app", "list", "--display-name", display_name])
    if not isinstance(apps, list):
        raise BootstrapError("Não foi possível consultar App Registrations.")
    if len(apps) > 1:
        raise BootstrapError(
            f"Há {len(apps)} App Registrations chamadas '{display_name}'. Resolva a ambiguidade antes de continuar."
        )
    return (apps[0] if apps else None), len(apps)


def _ensure_service_principal(app_id: str) -> bool:
    found = _run(["az", "ad", "sp", "show", "--id", app_id, "--output", "none"], check=False)
    if found.returncode == 0:
        return False
    _run(["az", "ad", "sp", "create", "--id", app_id, "--output", "none"])
    return True


def _secret_metadata(vault: str, secret_name: str) -> dict[str, Any] | None:
    result = _run(
        [
            "az",
            "keyvault",
            "secret",
            "show",
            "--vault-name",
            vault,
            "--name",
            secret_name,
            "--query",
            "{enabled:attributes.enabled,tags:tags}",
            "--output",
            "json",
        ],
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise BootstrapError("Metadados do segredo no Key Vault estão inválidos.") from exc
    return data if isinstance(data, dict) else None


def _create_app(display_name: str) -> dict[str, Any]:
    data = _json(
        [
            "az",
            "ad",
            "app",
            "create",
            "--display-name",
            display_name,
            "--sign-in-audience",
            "AzureADMyOrg",
            "--query",
            "{id:id,appId:appId,displayName:displayName}",
        ]
    )
    if not isinstance(data, dict) or not data.get("id") or not data.get("appId"):
        raise BootstrapError("App Registration foi criada, mas Azure CLI não retornou id/appId válidos.")
    return data


def _create_and_store_secret(*, app_id: str, vault: str, secret_name: str) -> None:
    password_result = _run(
        [
            "az",
            "ad",
            "app",
            "credential",
            "reset",
            "--id",
            app_id,
            "--append",
            "--display-name",
            "reqsys-teams-bot-dev-bootstrap",
            "--years",
            "1",
            "--query",
            "password",
            "--output",
            "tsv",
        ],
        sensitive=True,
    )
    client_secret = (password_result.stdout or "").strip()
    if not client_secret:
        raise BootstrapError("Microsoft Entra não retornou o novo segredo do aplicativo.")

    expires = (datetime.now(timezone.utc) + timedelta(days=365)).replace(microsecond=0)
    expires_text = expires.isoformat().replace("+00:00", "Z")
    _run(
        [
            "az",
            "keyvault",
            "secret",
            "set",
            "--vault-name",
            vault,
            "--name",
            secret_name,
            "--value",
            client_secret,
            "--expires",
            expires_text,
            "--tags",
            f"app-id={app_id}",
            "reqsys=true",
            "environment=dev",
            "component=teams-bot",
            "managed-by=human-bootstrap",
            "--output",
            "none",
        ],
        sensitive=True,
    )
    client_secret = ""  # noqa: F841 - redução explícita do tempo de vida da referência em memória.


def bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise BootstrapError(f"Confirmação inválida. Use --confirm {CONFIRMATION}")

    account = _account()
    tenant_id = str(account["tenantId"])
    if args.tenant_id and tenant_id.lower() != args.tenant_id.lower():
        raise BootstrapError(
            f"Tenant ativo ({tenant_id}) difere do tenant esperado ({args.tenant_id}). Nenhuma alteração foi feita."
        )

    app, _ = _find_app(args.app_display_name)
    created_app = False
    created_sp = False
    object_id = ""

    try:
        if app is None:
            app = _create_app(args.app_display_name)
            created_app = True
        object_id = str(app.get("id") or "")
        app_id = str(app.get("appId") or "")
        if not object_id or not app_id:
            raise BootstrapError("App Registration encontrada sem id/appId válidos.")

        created_sp = _ensure_service_principal(app_id)

        metadata = _secret_metadata(args.vault_name, args.secret_name)
        secret_created = False
        if metadata is not None:
            tags = metadata.get("tags") or {}
            tagged_app_id = str(tags.get("app-id") or "") if isinstance(tags, dict) else ""
            if tagged_app_id.lower() != app_id.lower():
                raise BootstrapError(
                    f"O segredo {args.secret_name} já existe, mas a tag app-id não corresponde à identidade dedicada."
                )
            if metadata.get("enabled") is False:
                raise BootstrapError(f"O segredo {args.secret_name} existe, mas está desabilitado.")
        else:
            _create_and_store_secret(app_id=app_id, vault=args.vault_name, secret_name=args.secret_name)
            secret_created = True

        return {
            "schema_version": "1.0.0",
            "status": "ready",
            "environment": "dev",
            "tenant_id": tenant_id,
            "app_display_name": args.app_display_name,
            "app_id": app_id,
            "created_app": created_app,
            "created_service_principal": created_sp,
            "secret_store": "Azure Key Vault",
            "secret_name": args.secret_name,
            "secret_created": secret_created,
            "secret_value_exposed": False,
            "next_action": "Executar Teams Bot DEV Provision para criar o Azure Bot, canal Teams e configurar reqsys-api-dev.",
        }
    except Exception:
        if created_app and object_id:
            _run(["az", "ad", "app", "delete", "--id", object_id], check=False)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap administrativo da identidade dedicada do Teams Bot DEV")
    parser.add_argument("--confirm", required=True, help=f"confirmação literal: {CONFIRMATION}")
    parser.add_argument("--tenant-id", default="", help="tenant esperado; se informado, bloqueia execução em tenant diferente")
    parser.add_argument("--app-display-name", default=DEFAULT_APP_NAME)
    parser.add_argument("--vault-name", default=DEFAULT_VAULT)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    parser.add_argument("--output", default="teams-bot-dev-identity-bootstrap.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        evidence = bootstrap(args)
        output = Path(args.output)
        output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False))
        return 0
    except BootstrapError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
