#!/usr/bin/env python3
"""Bootstrap administrativo único da identidade do Azure Bot DEV.

O script deve ser executado por uma conta Microsoft Entra autorizada a criar/gerir
App Registrations e a gravar o segredo dedicado no Azure Key Vault. O valor do
segredo nunca é impresso, salvo em arquivo ou retornado na evidência.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CONFIRMATION = "CRIAR-IDENTIDADE-TEAMS-BOT-DEV"
DEFAULT_APP_NAME = "ReqSys Teams Bot DEV"
DEFAULT_VAULT = "kv-reqsys-ccp"
DEFAULT_SECRET_NAME = "reqsys-teams-bot-dev-secret"
EXPECTED_SIGN_IN_AUDIENCE = "AzureADMyOrg"
VAULT_WRITE_ROLE = "Key Vault Secrets Officer"

REMEDIATION = {
    "entra_credential_reset": (
        "A conta autenticada não conseguiu emitir o client secret da App Registration. "
        "Garanta permissão de proprietário sobre o aplicativo (ou Application Administrator) e repita."
    ),
    "keyvault_secret_set": (
        f"A conta autenticada não conseguiu gravar o segredo no Key Vault. "
        f"Conceda '{VAULT_WRITE_ROLE}' sobre o cofre alvo e repita. "
        "Nenhum segredo permaneceu ativo: a credencial recém-emitida foi revogada."
    ),
}


class BootstrapError(RuntimeError):
    pass


def _cli() -> str:
    """Resolve o executável do Azure CLI sem depender de shell."""
    for candidate in ("az", "az.cmd", "az.bat"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise BootstrapError(
        "Azure CLI não encontrado no PATH. Instale o 'az' e execute 'az login' antes do bootstrap."
    )


def _run(
    args: list[str],
    *,
    check: bool = True,
    sensitive: bool = False,
    stage: str = "",
) -> subprocess.CompletedProcess[str]:
    resolved = [_cli(), *args[1:]] if args and args[0] == "az" else args
    try:
        result = subprocess.run(
            resolved,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        raise BootstrapError(f"Não foi possível executar o Azure CLI: {exc}") from exc
    if check and result.returncode != 0:
        if sensitive:
            hint = REMEDIATION.get(stage, "")
            suffix = f" {hint}" if hint else ""
            raise BootstrapError(
                f"Falha em operação sensível ({stage or 'desconhecida'}); "
                f"detalhes foram suprimidos para não expor credenciais.{suffix}"
            )
        detail = (result.stderr or result.stdout or "erro sem detalhe").strip()
        prefix = f"[{stage}] " if stage else ""
        raise BootstrapError(f"{prefix}{detail[:1200]}")
    return result


def _json(args: list[str], *, stage: str = "") -> Any:
    result = _run([*args, "--output", "json"], stage=stage)
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise BootstrapError("Azure CLI retornou JSON inválido.") from exc


def _account() -> dict[str, Any]:
    data = _json(["az", "account", "show"], stage="account_show")
    if not isinstance(data, dict) or not data.get("tenantId"):
        raise BootstrapError("Sessão Azure inválida. Execute 'az login' com a conta administrativa correta.")
    return data


def _assert_vault_reachable(vault: str) -> None:
    """Falha antes de qualquer mutação quando o cofre alvo não está acessível."""
    probe = _run(
        ["az", "keyvault", "secret", "list", "--vault-name", vault, "--maxresults", "1", "--output", "none"],
        check=False,
    )
    if probe.returncode != 0:
        raise BootstrapError(
            f"O cofre '{vault}' não está acessível para esta conta. "
            f"Conceda '{VAULT_WRITE_ROLE}' sobre o cofre (ou selecione a assinatura correta) antes do bootstrap. "
            "Nenhuma App Registration foi criada."
        )


def _find_app(display_name: str) -> tuple[dict[str, Any] | None, int]:
    apps = _json(["az", "ad", "app", "list", "--display-name", display_name], stage="app_list")
    if not isinstance(apps, list):
        raise BootstrapError("Não foi possível consultar App Registrations.")
    exact = [app for app in apps if str(app.get("displayName") or "") == display_name]
    if len(exact) > 1:
        raise BootstrapError(
            f"Há {len(exact)} App Registrations chamadas '{display_name}'. Resolva a ambiguidade antes de continuar."
        )
    return (exact[0] if exact else None), len(exact)


def _assert_reusable_app(app: dict[str, Any], display_name: str) -> None:
    audience = str(app.get("signInAudience") or "")
    if audience and audience != EXPECTED_SIGN_IN_AUDIENCE:
        raise BootstrapError(
            f"A App Registration '{display_name}' existe com signInAudience '{audience}', "
            f"mas o Azure Bot DEV exige '{EXPECTED_SIGN_IN_AUDIENCE}'. Nenhuma alteração foi feita."
        )


def _service_principal_exists(app_id: str) -> bool:
    return _run(["az", "ad", "sp", "show", "--id", app_id, "--output", "none"], check=False).returncode == 0


def _ensure_service_principal(app_id: str) -> bool:
    if _service_principal_exists(app_id):
        return False
    _run(["az", "ad", "sp", "create", "--id", app_id, "--output", "none"], stage="sp_create")
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


def _credential_key_ids(app_id: str) -> set[str]:
    data = _json(["az", "ad", "app", "credential", "list", "--id", app_id, "--query", "[].keyId"])
    if not isinstance(data, list):
        return set()
    return {str(item) for item in data if item}


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
        ],
        stage="app_create",
    )
    if not isinstance(data, dict) or not data.get("id") or not data.get("appId"):
        raise BootstrapError("App Registration foi criada, mas Azure CLI não retornou id/appId válidos.")
    return data


def _revoke_credential(app_id: str, key_id: str) -> None:
    _run(
        ["az", "ad", "app", "credential", "delete", "--id", app_id, "--key-id", key_id, "--output", "none"],
        check=False,
    )


def _create_and_store_secret(*, app_id: str, vault: str, secret_name: str) -> None:
    before = _credential_key_ids(app_id)
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
        stage="entra_credential_reset",
    )
    client_secret = (password_result.stdout or "").strip()
    if not client_secret:
        raise BootstrapError("Microsoft Entra não retornou o novo segredo do aplicativo.")

    emitted = sorted(_credential_key_ids(app_id) - before)

    expires = (datetime.now(timezone.utc) + timedelta(days=365)).replace(microsecond=0)
    expires_text = expires.isoformat().replace("+00:00", "Z")
    try:
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
            stage="keyvault_secret_set",
        )
    except BootstrapError:
        for key_id in emitted:
            _revoke_credential(app_id, key_id)
        raise
    finally:
        del client_secret  # redução explícita do tempo de vida da referência em memória.


def _plan(args: argparse.Namespace, tenant_id: str) -> dict[str, Any]:
    """Descreve o efeito do bootstrap sem executar nenhuma mutação."""
    app, _ = _find_app(args.app_display_name)
    app_id = str(app.get("appId") or "") if app else ""
    if app is not None:
        _assert_reusable_app(app, args.app_display_name)
    metadata = _secret_metadata(args.vault_name, args.secret_name)
    sp_exists = bool(app_id) and _service_principal_exists(app_id)
    actions: list[str] = []
    if app is None:
        actions.append(f"criar App Registration '{args.app_display_name}' ({EXPECTED_SIGN_IN_AUDIENCE})")
    if not sp_exists:
        actions.append("criar service principal da identidade dedicada")
    if metadata is None:
        actions.append(f"emitir client secret e gravá-lo em {args.vault_name}/{args.secret_name}")
    return {
        "schema_version": "1.1.0",
        "status": "dry_run",
        "environment": "dev",
        "tenant_id": tenant_id,
        "app_display_name": args.app_display_name,
        "app_id": app_id or None,
        "app_exists": app is not None,
        "service_principal_exists": sp_exists,
        "secret_exists": metadata is not None,
        "secret_store": "Azure Key Vault",
        "secret_name": args.secret_name,
        "secret_value_exposed": False,
        "planned_actions": actions or ["nenhuma; identidade dedicada já está completa"],
        "next_action": "Repetir sem --dry-run para aplicar o plano acima.",
    }


def bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise BootstrapError(f"Confirmação inválida. Use --confirm {CONFIRMATION}")

    account = _account()
    tenant_id = str(account["tenantId"])
    if args.tenant_id and tenant_id.lower() != args.tenant_id.lower():
        raise BootstrapError(
            f"Tenant ativo ({tenant_id}) difere do tenant esperado ({args.tenant_id}). Nenhuma alteração foi feita."
        )

    _assert_vault_reachable(args.vault_name)

    if args.dry_run:
        return _plan(args, tenant_id)

    app, _ = _find_app(args.app_display_name)
    created_app = False
    created_sp = False
    object_id = ""

    try:
        if app is None:
            app = _create_app(args.app_display_name)
            created_app = True
        else:
            _assert_reusable_app(app, args.app_display_name)
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
            "schema_version": "1.1.0",
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="apenas descreve o que seria criado; não altera Microsoft Entra nem Key Vault",
    )
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
