#!/usr/bin/env python3
"""Valida, sem rede, o inventário histórico da retirada do Fly.io."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "infra" / "fly-environments.json"
EXPECTED_ENVIRONMENTS = ["dev", "hml", "prod"]


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_permanently_retired(manifest: dict[str, Any]) -> bool:
    retirement = manifest.get("retirement", {})
    return (
        retirement.get("status") == "PERMANENTLY_RETIRED"
        and retirement.get("mutations_allowed") is False
        and retirement.get("reactivation_allowed") is False
    )


def _validate_retired_environment(
    env: str,
    cfg: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    initial_errors = len(errors)
    referenced_configs = {
        str(cfg[key])
        for key in ("fly_config", "backend_fly_config", "frontend_fly_config")
        if cfg.get(key)
    }
    if not referenced_configs:
        errors.append(f"{env}: inventario historico sem caminhos de manifestos")
    for relative_path in sorted(referenced_configs):
        if (ROOT / relative_path).exists():
            errors.append(
                f"{env}: manifesto Fly aposentado foi reintroduzido: {relative_path}"
            )

    for required_field in ("api_app", "frontend_app", "volume", "app_env"):
        if not cfg.get(required_field):
            errors.append(f"{env}: campo historico ausente: {required_field}")

    return {
        "environment": env,
        "ok": len(errors) == initial_errors,
        "status": "PERMANENTLY_RETIRED",
        "fly_config": cfg.get("fly_config"),
        "api_app": cfg.get("api_app"),
        "frontend_app": cfg.get("frontend_app"),
        "app_env": cfg.get("app_env"),
        "volume": cfg.get("volume"),
        "min_machines_running": cfg.get("min_machines_running"),
        "smoke_endpoints": cfg.get("smoke_endpoints", []),
        "approval_required": bool(cfg.get("approval_required")),
        "referenced_configs_absent": all(
            not (ROOT / relative_path).exists()
            for relative_path in referenced_configs
        ),
    }


def validate(manifest_path: Path = DEFAULT_MANIFEST) -> tuple[int, dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not manifest_path.exists():
        return 1, {"ok": False, "errors": [f"manifesto ausente: {manifest_path}"]}

    manifest = _load_manifest(manifest_path)
    retirement = manifest.get("retirement", {})
    if not _is_permanently_retired(manifest):
        errors.append(
            "retirement deve ser PERMANENTLY_RETIRED e bloquear mutacao/reativacao"
        )
    if manifest.get("canonical_environments") != EXPECTED_ENVIRONMENTS:
        errors.append("canonical_environments deve ser ['dev', 'hml', 'prod']")
    if manifest.get("promotion_order") != EXPECTED_ENVIRONMENTS:
        errors.append("promotion_order deve ser ['dev', 'hml', 'prod']")

    environments = manifest.get("environments", {})
    summaries: list[dict[str, Any]] = []
    for env in EXPECTED_ENVIRONMENTS:
        cfg = environments.get(env)
        if not isinstance(cfg, dict):
            errors.append(f"ambiente ausente no inventario historico: {env}")
            continue
        summaries.append(_validate_retired_environment(env, cfg, errors))

    for field in ("api_app", "frontend_app", "volume"):
        values = [
            cfg.get(field)
            for cfg in environments.values()
            if isinstance(cfg, dict) and cfg.get(field)
        ]
        if len(values) != len(set(values)):
            errors.append(f"{field} historico deve ser unico por ambiente")

    payload = {
        "ok": not errors,
        "schema_version": manifest.get("schema_version", "unknown"),
        "strategy": manifest.get("strategy"),
        "mode": "retirement_evidence",
        "retirement": retirement or None,
        "promotion_order": manifest.get("promotion_order"),
        "environments": summaries,
        "errors": errors,
        "warnings": warnings,
    }
    return (0 if not errors else 1), payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida inventario historico da aposentadoria Fly.io"
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output", help="Arquivo JSON de evidencia")
    args = parser.parse_args()

    exit_code, payload = validate(Path(args.manifest))
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
