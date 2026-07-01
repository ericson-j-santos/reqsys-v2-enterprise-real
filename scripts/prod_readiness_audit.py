#!/usr/bin/env python3
"""Auditoria automatizada de pendências de produção ReqSys/Fly.io.

Executa somente leituras públicas e gera artifact JSON/Markdown sem expor segredos.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_API_URL = "https://reqsys-api.fly.dev"
DEFAULT_APP_URL = "https://reqsys-app.fly.dev"
DEFAULT_OUTPUT = "artifacts/prod-readiness-audit.json"
EXPECTED_REDIRECTS = [
    "https://reqsys-app.fly.dev/auth/callback.html",
    "https://reqsys-app.fly.dev",
    "https://reqsys-app-stg.fly.dev/auth/callback.html",
]
REQUIRED_SECRET_KEYS = {
    "APP_ENV", "ALLOW_DEMO_LOGIN", "JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE",
    "APP_PUBLIC_URL", "API_PUBLIC_URL", "AZURE_TENANT_ID", "AZURE_CLIENT_ID",
}
SMOKE_PATHS = ["/health", "/api/runtime/status", "/api/runtime/health", "/api/runtime/readiness", "/api/runtime/liveness", "/v1/auth/config"]

@dataclass(frozen=True)
class Check:
    id: str
    area: str
    status: str
    human_required: bool
    detail: str
    evidence: Any = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_json(url: str, timeout: float) -> tuple[int | None, dict[str, Any] | None, str | None, int | None]:
    started = time.monotonic()
    try:
        req = Request(url, headers={"Accept": "application/json", "X-Correlation-ID": "prod-readiness-audit"})
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URLs públicas controladas por argumento operacional
            body = resp.read(65536)
            latency = int((time.monotonic() - started) * 1000)
            try:
                payload = json.loads(body.decode("utf-8")) if body else None
            except json.JSONDecodeError:
                payload = None
            return resp.status, payload, None, latency
    except HTTPError as exc:
        return exc.code, None, f"http_{exc.code}", int((time.monotonic() - started) * 1000)
    except (TimeoutError, URLError, OSError) as exc:
        return None, None, type(exc).__name__, int((time.monotonic() - started) * 1000)


def fly_secret_names(app: str) -> tuple[set[str], str | None]:
    try:
        proc = subprocess.run(["fly", "secrets", "list", "--app", app, "--json"], text=True, capture_output=True, timeout=30, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return set(), type(exc).__name__
    if proc.returncode != 0:
        return set(), proc.stderr.strip() or proc.stdout.strip() or f"fly_exit_{proc.returncode}"
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return set(), "invalid_fly_json"
    names = {str(item.get("Name") or item.get("name")) for item in payload if isinstance(item, dict)}
    return {name for name in names if name and name != "None"}, None


def build_audit(api_url: str, app_url: str, fly_app: str, timeout: float, check_fly: bool) -> dict[str, Any]:
    checks: list[Check] = []
    auth_status, auth_payload, auth_error, auth_latency = get_json(f"{api_url}/v1/auth/config", timeout)
    data = auth_payload.get("data", {}) if isinstance(auth_payload, dict) else {}
    expected_redirect = data.get("expected_redirect_uri") if isinstance(data, dict) else None
    checks.append(Check(
        "azure_redirect_uri", "auth_azure", "ok" if expected_redirect == f"{app_url}/auth/callback.html" else "action_required",
        expected_redirect != f"{app_url}/auth/callback.html",
        "Callback público esperado deve estar refletido em /v1/auth/config e registrado no Entra ID.",
        {"http": auth_status, "expected_redirect_uri": expected_redirect, "required_entra_redirects": EXPECTED_REDIRECTS, "latency_ms": auth_latency, "error": auth_error},
    ))
    checks.append(Check(
        "auth_demo_disabled", "security", "ok" if data.get("demo_login_enabled") is False else "blocked",
        data.get("demo_login_enabled") is not False,
        "Produção exige ALLOW_DEMO_LOGIN=false e demo_login_enabled=false.",
        {"demo_login_enabled": data.get("demo_login_enabled"), "environment": data.get("environment")},
    ))
    checks.append(Check(
        "azure_public_config", "auth_azure", "ok" if data.get("azure_enabled") and data.get("auth_status") == "ready" and not data.get("missing_fields") else "blocked",
        not (data.get("azure_enabled") and data.get("auth_status") == "ready" and not data.get("missing_fields")),
        "AZURE_TENANT_ID/AZURE_CLIENT_ID precisam estar configurados no backend.",
        {"azure_enabled": data.get("azure_enabled"), "auth_status": data.get("auth_status"), "missing_fields": data.get("missing_fields")},
    ))
    smoke = []
    for path in SMOKE_PATHS:
        status, payload, error, latency = get_json(f"{api_url}{path}", timeout)
        smoke.append({"path": path, "http": status, "ok": status == 200, "latency_ms": latency, "error": error, "status": (payload or {}).get("status") if isinstance(payload, dict) else None})
    checks.append(Check("public_smoke", "runtime", "ok" if all(item["ok"] for item in smoke) else "blocked", any(not item["ok"] for item in smoke), "Smoke público mínimo da API, incluindo /api/runtime/*.", smoke))
    if check_fly:
        names, error = fly_secret_names(fly_app)
        missing = sorted(REQUIRED_SECRET_KEYS - names)
        checks.append(Check("fly_secrets_presence", "secrets", "ok" if not missing and not error else "action_required", bool(missing or error), "Validação sem valores: confirma presença nominal dos secrets obrigatórios no Fly.io.", {"app": fly_app, "missing_keys": missing, "error": error, "checked_keys": sorted(REQUIRED_SECRET_KEYS)}))
    else:
        checks.append(Check("fly_secrets_presence", "secrets", "manual", True, "Execute com --check-fly para validar nomes de secrets via flyctl, sem revelar valores.", {"app": fly_app, "required_keys": sorted(REQUIRED_SECRET_KEYS)}))
    governance = ["aprovacao_qa", "aprovacao_ops", "janela_implantacao", "plano_rollback"]
    checks.append(Check("governance_approvals", "governance", "manual", True, "Aprovações e janela de implantação continuam humanas/processuais.", {"pending": governance}))
    checks.append(Check("corporate_domain", "dns", "recommended", True, "Domínio corporativo é recomendado, não bloqueante para runtime .fly.dev.", {"current_app_url": app_url, "current_api_url": api_url}))
    blocked = sum(c.status == "blocked" for c in checks)
    action = sum(c.status in {"action_required", "manual"} for c in checks)
    status = "blocked" if blocked else "action_required" if action else "ready"
    return {"schema_version": "1.0.0", "source": "prod-readiness-audit", "validated_at": now(), "status": status, "blocked_count": blocked, "action_required_count": action, "checks": [asdict(c) for c in checks]}


def write_markdown(report: dict[str, Any], path: Path) -> None:
    icons = {"ok": "✅", "blocked": "🔴", "action_required": "🟡", "manual": "🟡", "recommended": "🟢"}
    lines = ["# Levantamento automatizado — produção ReqSys/Fly.io", "", f"Status: **{report['status']}**", f"Validado em: `{report['validated_at']}`", "", "| Área | Check | Status | Humano? | Detalhe |", "|---|---|---|---|---|"]
    for c in report["checks"]:
        lines.append(f"| {c['area']} | `{c['id']}` | {icons.get(c['status'], '•')} {c['status']} | {'sim' if c['human_required'] else 'não'} | {c['detail']} |")
    lines.append("")
    lines.append("## Evidência JSON")
    lines.append(f"Arquivo pareado: `{path.with_suffix('.json')}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audita pendências de produção ReqSys/Fly.io")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--app-url", default=DEFAULT_APP_URL)
    parser.add_argument("--fly-app", default="reqsys-api")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--check-fly", action="store_true")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", default="")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    api_url = args.api_url.rstrip("/")
    app_url = args.app_url.rstrip("/")
    report = build_audit(api_url, app_url, args.fly_app, args.timeout, args.check_fly)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.markdown_output:
        md = Path(args.markdown_output)
        md.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(report, md)
    print(f"prod_readiness_audit={report['status']} blocked={report['blocked_count']} action_required={report['action_required_count']} output={output}")
    return 1 if args.strict and report["blocked_count"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
