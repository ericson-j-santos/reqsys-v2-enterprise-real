#!/usr/bin/env python3
"""Configura secrets de autenticação Azure AD no Fly.io.

Estratégia:
1. Usa inputs explícitos quando fornecidos.
2. Se ausentes, tenta resolver valores no cofre ReqSys via /v1/cofre/segredos/{key}.
3. Aplica secrets no Fly.io usando flyctl.
4. Valida /v1/auth/config após a configuração.

O script nunca imprime valores secretos. Quando executado no GitHub Actions,
adiciona máscara para tenant/client id resolvidos dinamicamente.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class ConfigError(RuntimeError):
    """Erro operacional de configuração."""


@dataclass(frozen=True)
class ConfiguracaoAuth:
    tenant_id: str
    client_id: str
    fonte_tenant: str
    fonte_client: str


def _mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}")


def _cofre_get(cofre_api_url: str, vault_token: str, key: str) -> str | None:
    if not cofre_api_url or not vault_token:
        return None

    endpoint = cofre_api_url.rstrip("/") + f"/v1/cofre/segredos/{key}"
    request = urllib.request.Request(
        endpoint,
        headers={
            "Accept": "application/json",
            "X-Vault-Token": vault_token,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # nosec B310 - URL controlada por operador
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise ConfigError(f"Cofre retornou HTTP {exc.code} para a chave {key}") from exc
    except urllib.error.URLError as exc:
        raise ConfigError(f"Falha de rede ao consultar cofre para a chave {key}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Cofre retornou JSON inválido para a chave {key}") from exc

    value = payload.get("data", {}).get("value")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _resolver_valor(
    *,
    explicit_value: str,
    cofre_api_url: str,
    vault_token: str,
    cofre_key: str,
    label: str,
) -> tuple[str, str]:
    if explicit_value.strip():
        return explicit_value.strip(), "workflow_input"

    cofre_value = _cofre_get(cofre_api_url, vault_token, cofre_key)
    if cofre_value:
        return cofre_value, f"cofre:{cofre_key}"

    raise ConfigError(
        f"{label} não encontrado. Informe input manual ou grave a chave {cofre_key} no cofre."
    )


def resolver_configuracao(args: argparse.Namespace) -> ConfiguracaoAuth:
    tenant_id, fonte_tenant = _resolver_valor(
        explicit_value=args.azure_tenant_id or "",
        cofre_api_url=args.cofre_api_url or "",
        vault_token=args.vault_token or "",
        cofre_key=args.cofre_tenant_key,
        label="AZURE_TENANT_ID",
    )
    client_id, fonte_client = _resolver_valor(
        explicit_value=args.azure_client_id or "",
        cofre_api_url=args.cofre_api_url or "",
        vault_token=args.vault_token or "",
        cofre_key=args.cofre_client_key,
        label="AZURE_CLIENT_ID",
    )

    _mask(tenant_id)
    _mask(client_id)

    return ConfiguracaoAuth(
        tenant_id=tenant_id,
        client_id=client_id,
        fonte_tenant=fonte_tenant,
        fonte_client=fonte_client,
    )


def executar(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    safe_cmd = ["***" if "AZURE_" in part else part for part in cmd]
    print("Executando:", " ".join(safe_cmd))
    completed = subprocess.run(cmd, check=False, text=True, env=env or os.environ.copy())
    if completed.returncode != 0:
        raise ConfigError(f"Comando falhou com exit code {completed.returncode}")


def aplicar_fly(args: argparse.Namespace, config: ConfiguracaoAuth) -> None:
    fly_token = args.fly_api_token or os.getenv("FLY_API_TOKEN", "")
    if not fly_token.strip():
        raise ConfigError("FLY_API_TOKEN não configurado")

    env = os.environ.copy()
    env["FLY_API_TOKEN"] = fly_token

    comando = [
        "flyctl",
        "secrets",
        "set",
        f"APP_ENV={args.app_env}",
        "ALLOW_DEMO_LOGIN=false",
        f"APP_PUBLIC_URL={args.app_public_url}",
        f"API_PUBLIC_URL={args.api_public_url}",
        f"AZURE_TENANT_ID={config.tenant_id}",
        f"AZURE_CLIENT_ID={config.client_id}",
        "-a",
        args.fly_app,
    ]
    executar(comando, env=env)


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # nosec B310 - URL controlada por operador
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - relatório operacional
        raise ConfigError(f"Falha ao validar {url}: {exc}") from exc


def validar(args: argparse.Namespace) -> dict[str, Any]:
    endpoint = args.api_public_url.rstrip("/") + "/v1/auth/config"
    ultimo_payload: dict[str, Any] | None = None

    for tentativa in range(1, args.validation_attempts + 1):
        try:
            payload = _get_json(endpoint)
            ultimo_payload = payload
            data = payload.get("data", {})
            if (
                payload.get("success") is True
                and data.get("azure_enabled") is True
                and data.get("auth_status") == "ready"
                and data.get("missing_fields") in ([], None)
                and (data.get("expected_redirect_uri") or "").rstrip("/") == args.app_public_url.rstrip("/")
            ):
                return {
                    "success": True,
                    "endpoint": endpoint,
                    "attempt": tentativa,
                    "data": {
                        "azure_enabled": data.get("azure_enabled"),
                        "auth_status": data.get("auth_status"),
                        "missing_fields": data.get("missing_fields"),
                        "expected_redirect_uri": data.get("expected_redirect_uri"),
                        "demo_login_enabled": data.get("demo_login_enabled"),
                        "environment": data.get("environment"),
                    },
                }
        except ConfigError:
            if tentativa == args.validation_attempts:
                raise

        time.sleep(args.validation_interval_seconds)

    return {
        "success": False,
        "endpoint": endpoint,
        "attempts": args.validation_attempts,
        "last_payload_sanitized": ultimo_payload,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configura auth Azure AD no Fly.io com fallback via cofre")
    parser.add_argument("--fly-app", required=True)
    parser.add_argument("--fly-api-token", default=os.getenv("FLY_API_TOKEN", ""))
    parser.add_argument("--app-env", default="production")
    parser.add_argument("--app-public-url", required=True)
    parser.add_argument("--api-public-url", required=True)
    parser.add_argument("--azure-tenant-id", default="")
    parser.add_argument("--azure-client-id", default="")
    parser.add_argument("--cofre-api-url", default=os.getenv("COFRE_API_URL", ""))
    parser.add_argument("--vault-token", default=os.getenv("VAULT_API_TOKEN", ""))
    parser.add_argument("--cofre-tenant-key", default="AZURE_TENANT_ID")
    parser.add_argument("--cofre-client-key", default="AZURE_CLIENT_ID")
    parser.add_argument("--validation-attempts", type=int, default=8)
    parser.add_argument("--validation-interval-seconds", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = resolver_configuracao(args)
    print(json.dumps({
        "status": "resolved",
        "tenant_source": config.fonte_tenant,
        "client_source": config.fonte_client,
        "fly_app": args.fly_app,
        "app_public_url": args.app_public_url,
        "api_public_url": args.api_public_url,
    }, ensure_ascii=False, indent=2))

    aplicar_fly(args, config)
    result = validar(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") is True else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ConfigError as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
