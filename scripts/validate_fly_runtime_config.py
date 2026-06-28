#!/usr/bin/env python3
"""Valida configuração versionada do Fly para o runtime P0 do ReqSys.

Não executa deploy e não lê secrets. O objetivo é impedir PRs que removam gates
mínimos, endpoints críticos ou arquivos necessários para publicação controlada.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "fly.toml",
    "Dockerfile.fly",
    "scripts/fly_boot.sh",
    "backend/requirements.txt",
    "backend/app/main.py",
    "backend/app/core/runtime_boot.py",
    "backend/app/api/monitoramento_operacional.py",
    "scripts/validate_public_runtime.py",
    "scripts/runtime_public_validator.py",
)

REQUIRED_FLY_SNIPPETS = (
    'app = "reqsys-api"',
    'dockerfile = "Dockerfile.fly"',
    'APP_ENV = "production"',
    'ALLOW_DEMO_LOGIN = "false"',
    'REQSYS_BOOT_FALLBACK = "true"',
    'REQSYS_BOOT_FALLBACK_DATABASE_URL = "sqlite:////tmp/reqsys-fallback.db"',
    'force_https = true',
    'path = "/health"',
)

REQUIRED_DOCKER_SNIPPETS = (
    "FROM python:3.12-slim",
    "COPY backend/requirements.txt",
    "COPY backend/app /app/app",
    "COPY scripts/fly_boot.sh",
    "HEALTHCHECK",
    "fly_boot.sh",
)

REQUIRED_MAIN_ENDPOINTS = (
    "@app.get('/')",
    "@app.get('/health')",
    "runtime_boot",
    "warm_database_on_startup",
    "'/api/runtime/health'",
    "'/api/runtime/readiness'",
    "'/api/runtime/liveness'",
    "'/api/runtime/metrics'",
    "'/v1/agile-runtime/resumo'",
)

REQUIRED_RUNTIME_ENDPOINTS = (
    "@router.get('/api/runtime/health')",
    "@router.get('/api/runtime/dashboard')",
    "@router.get('/api/runtime/readiness')",
    "@router.get('/api/runtime/liveness')",
    "@router.get('/api/runtime/metrics')",
)

REQUIRED_PRODUCTION_GATES = (
    "JWT_SECRET",
    "JWT_ISSUER",
    "JWT_AUDIENCE",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "ALLOW_DEMO_LOGIN",
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def contains_all(content: str, snippets: tuple[str, ...], errors: list[str], scope: str) -> None:
    for snippet in snippets:
        check(snippet in content, errors, f"{scope}: trecho obrigatório ausente: {snippet}")


def main() -> int:
    errors: list[str] = []

    for path in REQUIRED_FILES:
        check((ROOT / path).exists(), errors, f"arquivo obrigatório ausente: {path}")

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    fly = read("fly.toml")
    dockerfile = read("Dockerfile.fly")
    main_py = read("backend/app/main.py")
    runtime_py = read("backend/app/api/monitoramento_operacional.py")
    config_py = read("backend/app/core/config.py")

    contains_all(fly, REQUIRED_FLY_SNIPPETS, errors, "fly.toml")
    contains_all(dockerfile, REQUIRED_DOCKER_SNIPPETS, errors, "Dockerfile.fly")
    contains_all(main_py, REQUIRED_MAIN_ENDPOINTS, errors, "backend/app/main.py")
    contains_all(runtime_py, REQUIRED_RUNTIME_ENDPOINTS, errors, "monitoramento_operacional.py")
    contains_all(config_py, REQUIRED_PRODUCTION_GATES, errors, "config.py")

    check("*" not in re.findall(r'CORS_ORIGINS\s*=\s*"([^"]*)"', fly)[0], errors, "fly.toml: CORS_ORIGINS não pode conter wildcard")
    check("JWT_SECRET" not in fly, errors, "fly.toml: JWT_SECRET não deve ser versionado; use fly secrets")
    check("AZURE_CLIENT_SECRET" not in fly, errors, "fly.toml: AZURE_CLIENT_SECRET não deve ser versionado")

    result = {
        "ok": not errors,
        "schema_version": "1.0.0",
        "validated_files": list(REQUIRED_FILES),
        "runtime_endpoints": list(REQUIRED_RUNTIME_ENDPOINTS),
        "production_gates": list(REQUIRED_PRODUCTION_GATES),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
