#!/usr/bin/env python3
"""Valida disponibilidade, proteção e contrato do Control Center de notificações Teams."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "infra" / "fly-environments.json"
DEMO_EMAIL = "ericsonjosedossantos@tieri659.onmicrosoft.com"
PROTECTED_ENDPOINTS = (
    "/v1/teams-gateway/notificacoes/dashboard",
    "/v1/teams-gateway/notificacoes/fila?limit=5",
    "/v1/teams-gateway/notificacoes/dlq?limit=5",
    "/v1/teams-gateway/notificacoes/logs?limit=5",
)


@dataclass(frozen=True)
class HttpResult:
    status_code: int | None
    body: dict[str, Any] | list[Any] | None
    error: str | None
    latency_ms: int


RequestFn = Callable[..., HttpResult]


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 25.0,
) -> HttpResult:
    headers = {"Accept": "application/json", "User-Agent": "reqsys-teams-control-center-smoke/1.0"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            body = json.loads(raw) if raw.strip() else None
            return HttpResult(int(response.status), body, None, int((time.perf_counter() - started) * 1000))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw.strip() else None
        except json.JSONDecodeError:
            body = None
        return HttpResult(exc.code, body, str(exc.reason), int((time.perf_counter() - started) * 1000))
    except Exception as exc:  # noqa: BLE001 - coletor de evidência operacional
        return HttpResult(None, None, f"{type(exc).__name__}: {exc}", int((time.perf_counter() - started) * 1000))


def _check(name: str, result: HttpResult, *, expected: tuple[int, ...], detail: str = "") -> dict[str, Any]:
    ok = result.status_code in expected
    return {
        "name": name,
        "ok": ok,
        "status_code": result.status_code,
        "latency_ms": result.latency_ms,
        "detail": detail if ok else (result.error or f"HTTP esperado {expected}, recebido {result.status_code}"),
    }


def _validate_authenticated_payload(path: str, result: HttpResult) -> tuple[bool, str | None]:
    body = result.body
    if result.status_code != 200 or not isinstance(body, dict) or body.get("success") is not True:
        return False, f"contrato envelope inválido em {path}"
    data = body.get("data")
    if path.endswith("/dashboard"):
        required = {"schema_version", "pendentes", "processando", "enviados", "falhas", "cobertura"}
        if not isinstance(data, dict) or not required.issubset(data):
            return False, f"dashboard sem campos obrigatórios: {sorted(required)}"
    elif not isinstance(data, list):
        return False, f"coleção esperada em {path}"
    return True, None


def _resolve_token(
    api_url: str,
    *,
    timeout: float,
    request_fn: RequestFn,
) -> tuple[str | None, str, dict[str, Any]]:
    config = request_fn(f"{api_url}/v1/auth/config", timeout=timeout)
    config_check = _check("auth_config", config, expected=(200,))
    demo_enabled = bool(
        isinstance(config.body, dict)
        and isinstance(config.body.get("data"), dict)
        and config.body["data"].get("demo_login_enabled") is True
    )

    if demo_enabled:
        login = request_fn(
            f"{api_url}/v1/auth/login",
            method="POST",
            payload={"email": DEMO_EMAIL},
            timeout=timeout,
        )
        token = None
        if isinstance(login.body, dict) and isinstance(login.body.get("data"), dict):
            token = login.body["data"].get("access_token")
        login_check = _check("demo_login", login, expected=(200,))
        login_check["ok"] = bool(login_check["ok"] and token)
        if not login_check["ok"] and not login_check["detail"]:
            login_check["detail"] = "token ausente"
        return token, "demo_login" if token else "none", {
            "config": config_check,
            "login": login_check,
            "demo_login_enabled": True,
        }

    secret_token = os.getenv("REQSYS_TEAMS_SMOKE_BEARER_TOKEN", "").strip()
    return secret_token or None, "repository_secret" if secret_token else "none", {
        "config": config_check,
        "login": {
            "name": "demo_login",
            "ok": True,
            "status_code": None,
            "latency_ms": 0,
            "detail": "não aplicável; login demo desabilitado",
        },
        "demo_login_enabled": False,
    }


def validate_environment(
    environment: str,
    cfg: dict[str, Any],
    *,
    timeout: float,
    require_authenticated: bool,
    send_canary: bool,
    request_fn: RequestFn = _request_json,
) -> dict[str, Any]:
    api_url = str(cfg["api_url"]).rstrip("/")
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    health = request_fn(f"{api_url}/health", timeout=timeout)
    checks.append(_check("health", health, expected=(200,)))

    for path in PROTECTED_ENDPOINTS:
        clean_path = path.split("?", 1)[0]
        result = request_fn(f"{api_url}{path}", timeout=timeout)
        checks.append(_check(f"protected:{clean_path}", result, expected=(401, 403)))

    token, auth_source, auth_evidence = _resolve_token(api_url, timeout=timeout, request_fn=request_fn)
    authenticated_checks: list[dict[str, Any]] = []

    if token:
        for path in PROTECTED_ENDPOINTS:
            clean_path = path.split("?", 1)[0]
            result = request_fn(f"{api_url}{path}", token=token, timeout=timeout)
            contract_ok, contract_error = _validate_authenticated_payload(clean_path, result)
            authenticated_checks.append(
                {
                    "name": f"authenticated:{clean_path}",
                    "ok": contract_ok,
                    "status_code": result.status_code,
                    "latency_ms": result.latency_ms,
                    "detail": contract_error,
                }
            )
    else:
        warnings.append("smoke autenticado não executado: login demo desabilitado e token governado ausente")

    canary: dict[str, Any] = {"requested": send_canary, "executed": False, "ok": None}
    if send_canary:
        if not token:
            canary.update({"ok": False, "detail": "token administrativo indisponível"})
        else:
            correlation_id = f"teams-control-center-canary-{environment}-{uuid.uuid4()}"
            payload = {
                "origem": "sistema",
                "tipo_evento": "runtime_smoke_canary",
                "ambiente": environment,
                "correlation_id": correlation_id,
                "titulo": "ReqSys · Canary do Control Center Teams",
                "texto": "Validação governada de entrega e observabilidade do dashboard de notificações Teams.",
                "autor": "github-actions",
                "metadata": {"source": "teams-notification-control-center-smoke", "environment": environment},
                "destino_tipo": "auto",
                "modo": "auto",
                "permitir_fallback": True,
                "dry_run": False,
                "enviar_agora": True,
                "max_tentativas": 1,
            }
            result = request_fn(
                f"{api_url}/v1/teams-gateway/notificacoes/enfileirar",
                method="POST",
                payload=payload,
                token=token,
                timeout=timeout,
            )
            data = result.body.get("data") if isinstance(result.body, dict) else None
            delivered = bool(
                result.status_code == 200
                and isinstance(result.body, dict)
                and result.body.get("success") is True
                and isinstance(data, dict)
                and data.get("status_evento") == "ENVIADO"
                and data.get("correlation_id") == correlation_id
            )
            canary.update(
                {
                    "executed": True,
                    "ok": delivered,
                    "status_code": result.status_code,
                    "latency_ms": result.latency_ms,
                    "correlation_id": correlation_id,
                    "event_id": data.get("id_evento") if isinstance(data, dict) else None,
                    "delivery_status": data.get("status_evento") if isinstance(data, dict) else None,
                }
            )

    public_ok = all(item["ok"] for item in checks)
    auth_ok = bool(authenticated_checks) and all(item["ok"] for item in authenticated_checks)
    canary_ok = not send_canary or canary.get("ok") is True
    ok = public_ok and (auth_ok or not require_authenticated) and canary_ok

    if not public_ok or not canary_ok or (require_authenticated and not auth_ok):
        status = "failed"
    elif auth_ok:
        status = "healthy"
    else:
        status = "degraded"

    result_payload = {
        "schema_version": "1.0.0",
        "contract": "teams-notification-control-center-runtime-smoke",
        "environment": environment,
        "api_url": api_url,
        "generated_at_epoch": int(time.time()),
        "status": status,
        "ok": ok,
        "require_authenticated": require_authenticated,
        "auth_source": auth_source,
        "checks": checks,
        "auth_evidence": auth_evidence,
        "authenticated_checks": authenticated_checks,
        "canary": canary,
        "warnings": warnings,
    }
    canonical = json.dumps(result_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    result_payload["evidence_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return result_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida o runtime do Control Center Teams")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--environment", required=True, choices=["dev", "hml", "prod"])
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--output")
    parser.add_argument("--require-authenticated", action="store_true")
    parser.add_argument("--send-canary", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    cfg = (manifest.get("environments") or {}).get(args.environment)
    if not isinstance(cfg, dict):
        raise SystemExit(f"Ambiente ausente no manifest: {args.environment}")

    result = validate_environment(
        args.environment,
        cfg,
        timeout=args.timeout,
        require_authenticated=args.require_authenticated,
        send_canary=args.send_canary,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
