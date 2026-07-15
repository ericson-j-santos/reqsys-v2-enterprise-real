#!/usr/bin/env python3
"""Captura, guarda no cofre e sincroniza com o GitHub os 4 secrets exigidos
pelo workflow copilot-hitl-dev-component-homologation.yml (environment
"reqsys-power-platform-dev"): POWER_PLATFORM_ENVIRONMENT_URL,
POWER_PLATFORM_CLIENT_ID, POWER_PLATFORM_CLIENT_SECRET, POWER_PLATFORM_TENANT_ID.

Nunca imprime valores sensiveis (client secret). Client id, tenant id e a URL
do ambiente sao identificadores publicos, nao segredos, e podem ser exibidos.

Fluxo:
  1. capturar     -> resolve os 4 valores (explicito > env var > reaproveitar
                     AZURE_CLIENT_ID/AZURE_CLIENT_SECRET/AZURE_TENANT_ID ja
                     configurados localmente > prompt interativo) e grava no
                     cofre ReqSys via POST /v1/cofre/segredos (exige JWT admin).
  2. sincronizar  -> le os 4 valores do cofre via GET /v1/cofre/segredos/{key}
                     (X-Vault-Token) e aplica como GitHub Environment secrets
                     via `gh secret set --env reqsys-power-platform-dev`.

Uso tipico (reaproveitando a app "ReqSys Enterprise", que ja tem Application
User no Dataverse do ambiente ReqSys Dev com papel System Customizer):

    export REQSYS_ADMIN_TOKEN="<jwt admin>"
    export COFRE_API_URL="http://localhost:8000"
    python scripts/configurar_copilot_hitl_dev_secrets.py capturar --reuse-azure-app

    export COFRE_SERVICE_TOKEN="<vault token>"
    python scripts/configurar_copilot_hitl_dev_secrets.py sincronizar
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

KEYS = [
    "POWER_PLATFORM_ENVIRONMENT_URL",
    "POWER_PLATFORM_CLIENT_ID",
    "POWER_PLATFORM_CLIENT_SECRET",
    "POWER_PLATFORM_TENANT_ID",
]
SENSITIVE_KEYS = {"POWER_PLATFORM_CLIENT_SECRET"}

# Descoberto via `pac admin list` (leitura, sem escrita) - ambiente "ReqSys Dev".
DEFAULT_REQSYS_DEV_ENVIRONMENT_URL = "https://orge9b920f1.crm2.dynamics.com"

DEFAULT_GITHUB_ENVIRONMENT = "reqsys-power-platform-dev"


class OperacaoError(RuntimeError):
    pass


def _cofre_headers_admin(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _cofre_write(cofre_api_url: str, admin_token: str, key: str, value: str) -> None:
    endpoint = cofre_api_url.rstrip("/") + "/v1/cofre/segredos"
    body = json.dumps({"key": key, "value": value}).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=body, method="POST", headers=_cofre_headers_admin(admin_token)
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # nosec B310 - URL controlada por operador
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OperacaoError(f"Cofre recusou gravar '{key}': HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise OperacaoError(f"Falha de rede ao gravar '{key}' no cofre: {exc.reason}") from exc


def _cofre_read(cofre_api_url: str, vault_token: str, key: str) -> str | None:
    endpoint = cofre_api_url.rstrip("/") + f"/v1/cofre/segredos/{key}"
    request = urllib.request.Request(
        endpoint, headers={"Accept": "application/json", "X-Vault-Token": vault_token}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # nosec B310 - URL controlada por operador
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise OperacaoError(f"Cofre retornou HTTP {exc.code} ao ler '{key}'") from exc
    except urllib.error.URLError as exc:
        raise OperacaoError(f"Falha de rede ao ler '{key}' do cofre: {exc.reason}") from exc
    value = payload.get("data", {}).get("value")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _ler_env_file(path: str, key: str) -> str | None:
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


@dataclass(frozen=True)
class ValorResolvido:
    key: str
    value: str
    fonte: str


def resolver_valores(*, reuse_azure_app: bool, env_file: str, interativo: bool) -> list[ValorResolvido]:
    resolvidos: list[ValorResolvido] = []
    for key in KEYS:
        explicit = os.getenv(key, "").strip()
        if explicit:
            resolvidos.append(ValorResolvido(key, explicit, "env_var"))
            continue

        if key == "POWER_PLATFORM_ENVIRONMENT_URL":
            resolvidos.append(
                ValorResolvido(key, DEFAULT_REQSYS_DEV_ENVIRONMENT_URL, "default_reqsys_dev")
            )
            continue

        if reuse_azure_app:
            azure_key = {
                "POWER_PLATFORM_CLIENT_ID": "AZURE_CLIENT_ID",
                "POWER_PLATFORM_CLIENT_SECRET": "AZURE_CLIENT_SECRET",
                "POWER_PLATFORM_TENANT_ID": "AZURE_TENANT_ID",
            }[key]
            valor = os.getenv(azure_key, "").strip() or _ler_env_file(env_file, azure_key)
            if valor:
                resolvidos.append(ValorResolvido(key, valor, f"reuse:{azure_key}"))
                continue

        if not interativo:
            raise OperacaoError(
                f"Nao foi possivel resolver '{key}' (sem env var, sem --reuse-azure-app aplicavel, "
                "modo nao-interativo)."
            )
        prompt = f"Valor para {key}: "
        valor = getpass.getpass(prompt) if key in SENSITIVE_KEYS else input(prompt)
        valor = valor.strip()
        if not valor:
            raise OperacaoError(f"Valor vazio informado para '{key}'")
        resolvidos.append(ValorResolvido(key, valor, "prompt_interativo"))

    return resolvidos


def cmd_capturar(args: argparse.Namespace) -> int:
    admin_token = args.admin_token or os.getenv("REQSYS_ADMIN_TOKEN", "")
    cofre_api_url = args.cofre_api_url or os.getenv("COFRE_API_URL", "")
    if not admin_token or not cofre_api_url:
        print("erro: informe --admin-token/--cofre-api-url ou REQSYS_ADMIN_TOKEN/COFRE_API_URL", file=sys.stderr)
        return 2

    valores = resolver_valores(
        reuse_azure_app=args.reuse_azure_app,
        env_file=args.env_file,
        interativo=not args.non_interactive,
    )
    for item in valores:
        _cofre_write(cofre_api_url, admin_token, item.key, item.value)
        print(f"{item.key}: gravado no cofre (fonte={item.fonte})")
    return 0


def cmd_sincronizar(args: argparse.Namespace) -> int:
    vault_token = args.vault_token or os.getenv("COFRE_SERVICE_TOKEN", "") or os.getenv("VAULT_API_TOKEN", "")
    cofre_api_url = args.cofre_api_url or os.getenv("COFRE_API_URL", "")
    if not vault_token or not cofre_api_url:
        print("erro: informe --vault-token/--cofre-api-url ou COFRE_SERVICE_TOKEN/COFRE_API_URL", file=sys.stderr)
        return 2

    ok = True
    for key in KEYS:
        value = _cofre_read(cofre_api_url, vault_token, key)
        if value is None:
            print(f"{key}: nao encontrado no cofre -> pulei (rode 'capturar' primeiro)")
            ok = False
            continue
        completed = subprocess.run(
            ["gh", "secret", "set", key, "--env", args.github_environment, "--body", value],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            print(f"{key}: falha ao aplicar no GitHub -> {completed.stderr.strip()}")
            ok = False
            continue
        print(f"{key}: aplicado no GitHub Environment '{args.github_environment}'")
    return 0 if ok else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    capturar = sub.add_parser("capturar", help="Resolve os 4 valores e grava no cofre")
    capturar.add_argument("--admin-token", default=None)
    capturar.add_argument("--cofre-api-url", default=None)
    capturar.add_argument("--reuse-azure-app", action="store_true", help="Reaproveita AZURE_CLIENT_ID/SECRET/TENANT_ID locais")
    capturar.add_argument("--env-file", default=".env")
    capturar.add_argument("--non-interactive", action="store_true")
    capturar.set_defaults(func=cmd_capturar)

    sincronizar = sub.add_parser("sincronizar", help="Le do cofre e aplica como GitHub Environment secrets")
    sincronizar.add_argument("--vault-token", default=None)
    sincronizar.add_argument("--cofre-api-url", default=None)
    sincronizar.add_argument("--github-environment", default=DEFAULT_GITHUB_ENVIRONMENT)
    sincronizar.set_defaults(func=cmd_sincronizar)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return args.func(args)
    except OperacaoError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
