#!/usr/bin/env python3
"""Valida login (Azure AD + demo + bundle frontend) em todos os ambientes Fly.

Read-only para credenciais reais: não executa login interativo MSAL.
Usa `infra/fly-environments.json` como fonte canônica de URLs.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "infra" / "fly-environments.json"
DEMO_EMAIL = "ericsonjosedossantos@tieri659.onmicrosoft.com"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validar_frontend_auth_redirect import validate_public_frontend
from scripts.validar_login_azure_operacional import validar_config


@dataclass(frozen=True)
class LoginProbeResult:
    name: str
    ok: bool
    status_code: int | None
    detail: str | None = None
    has_token: bool = False


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[dict[str, Any] | None, int | None, str | None]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return body, int(response.status), None
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = None
        return body, exc.code, exc.reason
    except Exception as exc:  # noqa: BLE001 - evidence collector
        return None, None, str(exc)


def _probe_demo_login(api_url: str, *, timeout: float, expect_allowed: bool) -> LoginProbeResult:
    endpoint = api_url.rstrip("/") + "/v1/auth/login"
    body, status, error = _post_json(endpoint, {"email": DEMO_EMAIL}, timeout)
    has_token = bool(isinstance(body, dict) and body.get("success") and (body.get("data") or {}).get("access_token"))

    if error and status is None:
        return LoginProbeResult("demo_login", False, None, error)

    if expect_allowed:
        ok = status == 200 and has_token
        detail = None if ok else f"esperado 200 com token, recebido status={status}"
        return LoginProbeResult("demo_login", ok, status, detail, has_token)

    ok = status == 403
    detail = None if ok else f"esperado 403 em ambiente sem demo, recebido status={status}"
    return LoginProbeResult("demo_login", ok, status, detail, has_token)


def validate_environment_login(
    env_name: str,
    cfg: dict[str, Any],
    *,
    timeout: float,
) -> dict[str, Any]:
    api_url = str(cfg["api_url"]).rstrip("/")
    frontend_url = str(cfg["frontend_url"]).rstrip("/")
    app_env = str(cfg.get("app_env") or "")
    expect_demo_allowed = app_env == "development"

    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    try:
        azure_result = validar_config(api_url, frontend_url)
        checks["azure_config"] = azure_result
        if not azure_result["success"]:
            errors.extend(azure_result.get("errors") or [])
        for warning in azure_result.get("warnings") or []:
            if app_env == "development" and "demo_login_enabled" in warning:
                continue
            warnings.append(warning)
    except Exception as exc:  # noqa: BLE001
        checks["azure_config"] = {"success": False, "errors": [str(exc)]}
        errors.append(f"azure_config: {exc}")

    try:
        frontend_result = validate_public_frontend(frontend_url)
        checks["frontend_redirect"] = frontend_result
        if not frontend_result["success"]:
            errors.extend(frontend_result.get("errors") or [])
    except Exception as exc:  # noqa: BLE001
        checks["frontend_redirect"] = {"success": False, "errors": [str(exc)]}
        errors.append(f"frontend_redirect: {exc}")

    demo_probe = _probe_demo_login(api_url, timeout=timeout, expect_allowed=expect_demo_allowed)
    checks["demo_login"] = asdict(demo_probe)
    if not demo_probe.ok:
        label = "demo_login deve funcionar em dev" if expect_demo_allowed else "demo_login deve estar bloqueado fora de dev"
        errors.append(f"{label}: {demo_probe.detail or demo_probe.status_code}")

    if app_env == "production" and checks.get("azure_config", {}).get("data", {}).get("demo_login_enabled") is True:
        errors.append("demo_login_enabled não pode ser true em produção")

    operational_status = "ready"
    if errors:
        operational_status = "degraded" if any(
            checks.get(key, {}).get("success") for key in ("azure_config", "frontend_redirect")
        ) else "unavailable"

    return {
        "environment": env_name,
        "app_env": app_env,
        "api_url": api_url,
        "frontend_url": frontend_url,
        "expect_demo_allowed": expect_demo_allowed,
        "operational_status": operational_status,
        "login_ready": not errors,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def build_payload(
    *,
    manifest_path: Path,
    environment: str | None,
    timeout: float,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    environments_cfg = manifest.get("environments") or {}
    order = list(manifest.get("canonical_environments") or environments_cfg.keys())
    targets = [environment] if environment else order

    summaries = [
        validate_environment_login(name, environments_cfg[name], timeout=timeout)
        for name in targets
        if name in environments_cfg
    ]

    ready = sum(1 for item in summaries if item["login_ready"])
    blocking = [f"{item['environment']}: {err}" for item in summaries for err in item["errors"]]

    return {
        "schema_version": "1.0.0",
        "contract": "multi-environment-login-validation",
        "validated_at_epoch": int(time.time()),
        "summary": {
            "environments_total": len(summaries),
            "login_ready": ready,
            "login_failed": len(summaries) - ready,
            "overall_status": "ready" if ready == len(summaries) else "degraded" if ready else "unavailable",
        },
        "environments": summaries,
        "ok": ready == len(summaries),
        "blocking_issues": blocking,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida login em todos os ambientes ReqSys")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--environment", choices=["dev", "hml", "prod"])
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--output", help="Arquivo JSON de evidência")
    args = parser.parse_args()

    payload = build_payload(
        manifest_path=Path(args.manifest),
        environment=args.environment,
        timeout=args.timeout,
    )
    if args.output:
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
