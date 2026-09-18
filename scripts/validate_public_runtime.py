#!/usr/bin/env python3
"""Valida smoke público e readiness operacional do ReqSys.

Read-only, sem credenciais, sem dependências externas.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_ENDPOINTS = ("/health", "/api/runtime/health", "/api/runtime/readiness", "/api/runtime/liveness")
OPTIONAL_PUBLIC_EVIDENCE_ENDPOINTS = (
    "/", "/runtime", "/api/runtime/contracts", "/api/runtime/version", "/api/runtime/build-info",
    "/api/runtime/dependencies", "/api/runtime/metrics", "/api/runtime/dashboard", "/api/runtime/analytics",
)
DASHBOARD_ENDPOINTS = {"/runtime", "/api/runtime/dashboard"}
INCIDENT_ENDPOINTS = {"/api/runtime/analytics", "/api/runtime/dashboard"}
API_ENDPOINTS = {"/health", "/api/runtime/health", "/api/runtime/readiness", "/api/runtime/liveness"}
LOGIN_HINTS = ("login", "access_token", "auth")
ASSET_HINTS = ("/assets/", "src=", "href=")


@dataclass(frozen=True)
class EndpointResult:
    endpoint: str
    url: str
    ok: bool
    status_code: int | None
    elapsed_ms: int
    content_type: str | None
    error: str | None = None
    payload_keys: list[str] | None = None
    cors_allow_origin: str | None = None
    has_asset_reference: bool = False
    has_runtime_dashboard_marker: bool = False
    has_incident_marker: bool = False
    has_login_marker: bool = False


def _normalizar_base_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise ValueError("base-url deve iniciar com http:// ou https://")
    return base


def _ler_json_seguro(raw: bytes) -> tuple[dict[str, Any] | None, list[str] | None]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return None, None
    if isinstance(payload, dict):
        return payload, sorted(payload.keys())
    return None, None


def _text_markers(raw: bytes) -> dict[str, bool]:
    text = raw[:512_000].decode("utf-8", errors="ignore").lower()
    return {
        "has_asset_reference": any(hint in text for hint in ASSET_HINTS),
        "has_runtime_dashboard_marker": "runtime" in text and "dashboard" in text,
        "has_incident_marker": "incident" in text or "timeline" in text,
        "has_login_marker": any(hint in text for hint in LOGIN_HINTS),
    }


def validar_endpoint(base_url: str, endpoint: str, timeout: float, origin: str | None = None) -> EndpointResult:
    url = f"{base_url}{endpoint}"
    started = time.perf_counter()
    headers = {"Accept": "application/json, text/html", "User-Agent": "reqsys-runtime-smoke/1.1"}
    if origin:
        headers["Origin"] = origin
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL fornecida explicitamente pelo operador
            raw = response.read(512_000)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            _payload, payload_keys = _ler_json_seguro(raw)
            markers = _text_markers(raw)
            return EndpointResult(
                endpoint=endpoint,
                url=url,
                ok=200 <= int(response.status) < 300,
                status_code=int(response.status),
                elapsed_ms=elapsed_ms,
                content_type=response.headers.get("content-type"),
                payload_keys=payload_keys,
                cors_allow_origin=response.headers.get("access-control-allow-origin"),
                **markers,
            )
    except HTTPError as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return EndpointResult(endpoint, url, False, int(exc.code), elapsed_ms, exc.headers.get("content-type") if exc.headers else None, str(exc), cors_allow_origin=exc.headers.get("access-control-allow-origin") if exc.headers else None)
    except (TimeoutError, URLError, OSError) as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return EndpointResult(endpoint, url, False, None, elapsed_ms, None, f"{type(exc).__name__}: {exc}")


def _classificar(ok_percent: float, reachable: bool, dashboard_ready: bool, api_ready: bool) -> str:
    if not reachable:
        return "unavailable"
    if ok_percent >= 95 and dashboard_ready and api_ready:
        return "healthy"
    if ok_percent >= 60 and api_ready:
        return "partial"
    return "degraded"


def _readiness_payload(environment: str, base_url: str, results: list[EndpointResult], required_endpoints: tuple[str, ...]) -> dict[str, Any]:
    required = [r for r in results if r.endpoint in required_endpoints]
    reachable = any(r.ok for r in results)
    avg_ms = round(sum(r.elapsed_ms for r in results) / len(results), 2) if results else None
    ok_required = sum(1 for r in required if r.ok)
    readiness_percent = round(ok_required / len(required) * 100, 2) if required else 0.0
    by_endpoint = {r.endpoint: r for r in results}
    dashboard_ready = any(r.ok for r in results if r.endpoint in DASHBOARD_ENDPOINTS)
    api_ready = all(by_endpoint.get(endpoint) and by_endpoint[endpoint].ok for endpoint in API_ENDPOINTS if endpoint in required_endpoints)
    runtime_ready = bool(by_endpoint.get("/api/runtime/health") and by_endpoint["/api/runtime/health"].ok)
    evidence_ready = any(r.ok for r in results if r.endpoint in OPTIONAL_PUBLIC_EVIDENCE_ENDPOINTS)
    login_ready = any(r.has_login_marker for r in results)
    blocking = [f"{r.endpoint}: {r.status_code or 'no-http'} {r.error or ''}".strip() for r in required if not r.ok]
    status = _classificar(readiness_percent, reachable, dashboard_ready, api_ready)
    return {
        "environment": environment,
        "base_url": base_url,
        "reachable": reachable,
        "response_time": avg_ms,
        "dashboard_ready": dashboard_ready,
        "login_ready": login_ready,
        "api_ready": api_ready,
        "runtime_ready": runtime_ready,
        "evidence_ready": evidence_ready,
        "operational_status": status,
        "readiness_percent": readiness_percent,
        "blocking_issues": blocking,
        "next_actions": [] if status == "healthy" else ["Validar artifact public-runtime-validation.json", "Corrigir endpoints indisponíveis antes de promover ambiente", "Reexecutar smoke validator read-only"],
    }


def build_payload(base_url: str, environment: str, results: list[EndpointResult], required_endpoints: tuple[str, ...], optional_enabled: bool) -> dict[str, Any]:
    required_results = [r for r in results if r.endpoint in required_endpoints]
    optional_results = [r for r in results if r.endpoint not in required_endpoints]
    required_ok_count = sum(1 for r in required_results if r.ok)
    optional_ok_count = sum(1 for r in optional_results if r.ok)
    readiness = _readiness_payload(environment, base_url, results, required_endpoints)
    return {
        "schema_version": "1.3.0",
        "contract": "public-runtime-smoke-readiness",
        "environment": environment,
        "base_url": base_url,
        "validated_at_epoch": int(time.time()),
        "total": len(required_results),
        "ok": required_ok_count,
        "failed": len(required_results) - required_ok_count,
        "success_percentual": round(required_ok_count / len(required_results) * 100, 2) if required_results else 0.0,
        "optional_total": len(optional_results),
        "optional_ok": optional_ok_count,
        "optional_failed": len(optional_results) - optional_ok_count,
        "optional_success_percentual": round(optional_ok_count / len(optional_results) * 100, 2) if optional_results else None,
        "required_endpoints": list(required_endpoints),
        "optional_evidence_endpoints": list(OPTIONAL_PUBLIC_EVIDENCE_ENDPOINTS if optional_enabled else ()),
        "checks": {"frontend_loading": bool(next((r.ok for r in results if r.endpoint == "/"), False)), "assets": any(r.has_asset_reference for r in results), "cors_basic": any(r.cors_allow_origin for r in results), "incident_timeline": any(r.has_incident_marker or r.endpoint in INCIDENT_ENDPOINTS and r.ok for r in results)},
        "readiness": readiness,
        "results": [asdict(r) for r in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida smoke público do ReqSys no Fly/DuckDNS")
    parser.add_argument("--base-url", default="https://reqsys-api.fly.dev")
    parser.add_argument("--environment", default="prod")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--endpoint", action="append", dest="endpoints")
    parser.add_argument("--include-optional-evidence", action="store_true")
    parser.add_argument("--cors-origin", default="https://reqsys.example.com")
    parser.add_argument("--output", default="public-runtime-validation.json")
    parser.add_argument("--readiness-output", default="ops-readiness-report.json")
    args = parser.parse_args()

    base_url = _normalizar_base_url(args.base_url)
    required_endpoints = tuple(args.endpoints) if args.endpoints else DEFAULT_ENDPOINTS
    evidence_endpoints = required_endpoints + (OPTIONAL_PUBLIC_EVIDENCE_ENDPOINTS if args.include_optional_evidence else ())
    # Preserve order while removing duplicates.
    evidence_endpoints = tuple(dict.fromkeys(evidence_endpoints))
    results = [validar_endpoint(base_url, endpoint, args.timeout, args.cors_origin) for endpoint in evidence_endpoints]
    payload = build_payload(base_url, args.environment, results, required_endpoints, args.include_optional_evidence)

    with open(args.output, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    with open(args.readiness_output, "w", encoding="utf-8") as file:
        json.dump(payload["readiness"], file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] == payload["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
