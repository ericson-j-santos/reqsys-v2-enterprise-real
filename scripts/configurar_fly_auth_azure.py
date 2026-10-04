#!/usr/bin/env python3
"""Compatibilidade read-only para a antiga configuração Azure AD no Fly.io.

A capacidade de resolver credenciais, chamar ``flyctl`` e gravar secrets foi
removida. O helper de validação HTTP permanece para consumidores históricos que
somente inspecionam ``/v1/auth/config``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

FLYIO_RETIREMENT_GUARD = (
    "Fly.io foi retirado definitivamente em 2026-10-02; configurar secrets ou reativar apps esta bloqueado."
)


class ConfigError(RuntimeError):
    """Erro operacional de configuração."""


@dataclass(frozen=True)
class ConfiguracaoAuth:
    """Contrato legado sem capacidade de persistir valores em provedor."""

    tenant_id: str
    client_id: str
    fonte_tenant: str
    fonte_client: str


def aplicar_fly(args: argparse.Namespace | None, config: ConfiguracaoAuth | None) -> None:
    """Recusa permanentemente a antiga mutação de secrets."""

    raise ConfigError(FLYIO_RETIREMENT_GUARD)


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # nosec B310 - URL controlada por operador
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - relatório operacional legado
        raise ConfigError(f"Falha ao validar {url}: {exc}") from exc


def validar(args: argparse.Namespace) -> dict[str, Any]:
    """Valida um endpoint explicitamente informado, sem usar APIs do Fly.io."""

    endpoint = args.api_public_url.rstrip("/") + "/v1/auth/config"
    redirect_uri_esperado = args.app_public_url.rstrip("/") + "/auth/callback.html"
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
                and (data.get("expected_redirect_uri") or "").rstrip("/")
                == redirect_uri_esperado
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


def main() -> int:
    """Falha antes de ler credenciais, argumentos operacionais ou rede."""

    print(
        json.dumps(
            {"success": False, "status": "PERMANENTLY_RETIRED", "error": FLYIO_RETIREMENT_GUARD},
            ensure_ascii=False,
            indent=2,
        ),
        file=sys.stderr,
    )
    return 78


if __name__ == "__main__":
    raise SystemExit(main())
