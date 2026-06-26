#!/usr/bin/env python3
"""Valida a matriz canônica de ambientes Fly.io do ReqSys.

A validação é read-only: não consulta secrets, não executa deploy e não chama flyctl.
Ela garante que os artefatos versionados de IaC estejam alinhados ao manifesto de
ambientes, que não haja segredo materializado em TOML e que a promoção dev → hml →
prod tenha evidência mínima de smoke/approval gates.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "infra" / "fly-environments.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract(pattern: str, content: str, default: str | None = None) -> str | None:
    match = re.search(pattern, content, flags=re.MULTILINE)
    return match.group(1).strip() if match else default


def _extract_int(pattern: str, content: str, default: int | None = None) -> int | None:
    value = _extract(pattern, content)
    return int(value) if value is not None else default


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(_read(path))


def _validate_environment(env: str, cfg: dict[str, Any], manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> dict[str, Any]:
    fly_path = ROOT / cfg["fly_config"]
    if not fly_path.exists():
        errors.append(f"{env}: fly_config ausente: {cfg['fly_config']}")
        return {"environment": env, "ok": False, "fly_config": cfg["fly_config"]}

    content = _read(fly_path)
    app = _extract(r'^app\s*=\s*"([^"]+)"', content)
    app_env = _extract(r'^\s*APP_ENV\s*=\s*"([^"]+)"', content)
    public_env = _extract(r'^\s*PUBLIC_ENVIRONMENT\s*=\s*"([^"]+)"', content)
    volume = _extract(r'^\s*source\s*=\s*"([^"]+)"', content)
    min_machines = _extract_int(r'^\s*min_machines_running\s*=\s*(\d+)', content)
    health_path = _extract(r'^\s*path\s*=\s*"([^"]+)"', content)
    cors = _extract(r'^\s*CORS_ORIGINS\s*=\s*"([^"]+)"', content, "") or ""

    if app != cfg["api_app"]:
        errors.append(f"{env}: app Fly esperado {cfg['api_app']}, encontrado {app}")
    if (app_env or public_env) != cfg["app_env"]:
        errors.append(f"{env}: APP_ENV/PUBLIC_ENVIRONMENT esperado {cfg['app_env']}, encontrado {app_env or public_env}")
    if volume != cfg["volume"]:
        errors.append(f"{env}: volume esperado {cfg['volume']}, encontrado {volume}")
    if min_machines != cfg["min_machines_running"]:
        errors.append(f"{env}: min_machines_running esperado {cfg['min_machines_running']}, encontrado {min_machines}")
    if "*" in cors:
        errors.append(f"{env}: CORS_ORIGINS não pode conter wildcard")
    if health_path != "/health":
        errors.append(f"{env}: health check Fly deve apontar para /health")
    if not cfg.get("smoke_endpoints"):
        errors.append(f"{env}: smoke_endpoints obrigatório")
    if env in {"hml", "prod"} and not cfg.get("approval_required"):
        errors.append(f"{env}: promotion gate exige approval_required=true")

    for secret_pattern in manifest.get("forbidden_versioned_secret_patterns", []):
        if re.search(rf'^\s*{re.escape(secret_pattern)}\s*=', content, flags=re.MULTILINE):
            errors.append(f"{env}: segredo versionado proibido em {cfg['fly_config']}: {secret_pattern}")
    for secret_name in cfg.get("required_secret_names", []):
        if not re.fullmatch(r"[A-Z0-9_]{3,64}", secret_name):
            errors.append(f"{env}: nome de secret inválido: {secret_name}")
    if env == "prod" and cfg.get("app_env") != "production":
        warnings.append("prod: app_env não está como production")

    return {
        "environment": env,
        "ok": True,
        "fly_config": cfg["fly_config"],
        "api_app": app,
        "app_env": app_env or public_env,
        "volume": volume,
        "min_machines_running": min_machines,
        "smoke_endpoints": cfg.get("smoke_endpoints", []),
        "approval_required": bool(cfg.get("approval_required")),
    }


def validate(manifest_path: Path = DEFAULT_MANIFEST) -> tuple[int, dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not manifest_path.exists():
        return 1, {"ok": False, "errors": [f"manifesto ausente: {manifest_path}"]}

    manifest = _load_manifest(manifest_path)
    expected_order = ["dev", "hml", "prod"]
    if manifest.get("canonical_environments") != expected_order:
        errors.append("canonical_environments deve ser ['dev', 'hml', 'prod']")
    if manifest.get("promotion_order") != expected_order:
        errors.append("promotion_order deve ser ['dev', 'hml', 'prod']")

    environments = manifest.get("environments", {})
    summaries = []
    for env in expected_order:
        cfg = environments.get(env)
        if not cfg:
            errors.append(f"ambiente ausente no manifesto: {env}")
            continue
        summaries.append(_validate_environment(env, cfg, manifest, errors, warnings))

    apps = [env.get("api_app") for env in environments.values()]
    volumes = [env.get("volume") for env in environments.values()]
    if len(apps) != len(set(apps)):
        errors.append("api_app deve ser único por ambiente")
    if len(volumes) != len(set(volumes)):
        errors.append("volume deve ser único por ambiente")

    payload = {
        "ok": not errors,
        "schema_version": manifest.get("schema_version", "unknown"),
        "strategy": manifest.get("strategy"),
        "promotion_order": manifest.get("promotion_order"),
        "environments": summaries,
        "errors": errors,
        "warnings": warnings,
    }
    return (0 if not errors else 1), payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida sync enterprise Fly.io versionado")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Manifesto JSON de ambientes")
    parser.add_argument("--output", help="Arquivo JSON de evidência")
    args = parser.parse_args()

    exit_code, payload = validate(Path(args.manifest))
    if args.output:
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
