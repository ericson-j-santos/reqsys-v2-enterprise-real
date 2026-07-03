#!/usr/bin/env python3
"""Validação operacional do login Microsoft/Azure AD no ReqSys.

Uso:
    python scripts/validar_login_azure_operacional.py \
        --api-url https://reqsys-api.fly.dev \
        --expected-redirect-uri https://reqsys-app.fly.dev/auth/callback.html

O script não executa login interativo nem manipula credenciais. Ele valida se a API
está publicando configuração suficiente para o frontend renderizar o botão Microsoft
e iniciar o fluxo MSAL com segurança.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any


class ValidationError(RuntimeError):
    """Erro de validação operacional."""


def _get_json(url: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - URL controlada por operador
            status = response.status
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ValidationError(f"HTTP {exc.code} ao consultar {url}") from exc
    except urllib.error.URLError as exc:
        raise ValidationError(f"Falha de rede ao consultar {url}: {exc.reason}") from exc

    if status != 200:
        raise ValidationError(f"Status inesperado em {url}: {status}")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Resposta não é JSON válido em {url}") from exc

    if not isinstance(payload, dict):
        raise ValidationError("Resposta JSON não é objeto")
    return payload


def validar_config(api_url: str, expected_redirect_uri: str) -> dict[str, Any]:
    endpoint = api_url.rstrip("/") + "/v1/auth/config"
    payload = _get_json(endpoint)
    data = payload.get("data", {})

    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("success") is not True:
        errors.append("Envelope success deve ser true")

    if data.get("azure_enabled") is not True:
        errors.append("azure_enabled deve ser true")

    if data.get("auth_status") != "ready":
        errors.append("auth_status deve ser ready")

    missing_fields = data.get("missing_fields")
    if missing_fields not in ([], None):
        errors.append(f"missing_fields deve estar vazio; atual={missing_fields}")

    if not data.get("azure_tenant_id"):
        errors.append("azure_tenant_id público está ausente")

    if not data.get("azure_client_id"):
        errors.append("azure_client_id público está ausente")

    actual_redirect = (data.get("expected_redirect_uri") or "").rstrip("/")
    expected_redirect = expected_redirect_uri.rstrip("/")
    if actual_redirect != expected_redirect:
        errors.append(
            "expected_redirect_uri divergente: "
            f"esperado={expected_redirect} atual={actual_redirect or '<ausente>'}"
        )

    if data.get("demo_login_enabled") is True:
        warnings.append("demo_login_enabled está true; isso é bloqueante em produção")

    return {
        "validated_at": datetime.now(UTC).isoformat(),
        "endpoint": endpoint,
        "success": not errors,
        "errors": errors,
        "warnings": warnings,
        "data": {
            "azure_enabled": data.get("azure_enabled"),
            "auth_status": data.get("auth_status"),
            "missing_fields": data.get("missing_fields"),
            "expected_redirect_uri": data.get("expected_redirect_uri"),
            "demo_login_enabled": data.get("demo_login_enabled"),
            "environment": data.get("environment"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida configuração operacional Azure AD do ReqSys")
    parser.add_argument("--api-url", required=True, help="URL base da API, exemplo: https://reqsys-api.fly.dev")
    parser.add_argument("--expected-redirect-uri", required=True, help="Origem pública esperada do frontend")
    args = parser.parse_args()

    result = validar_config(args.api_url, args.expected_redirect_uri)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
