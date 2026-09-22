#!/usr/bin/env python3
"""Valida observabilidade runtime pública (E2E read-only).

Complementa o Public Runtime Evidence Gate strict com probes de
métricas, dashboard, analytics, página /runtime e propagação de correlation_id.
Sem credenciais, sem deploy, sem escrita em banco.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OBSERVABILITY_E2E_ENDPOINTS = (
    "/api/runtime/metrics",
    "/api/runtime/dashboard",
    "/api/runtime/analytics",
    "/runtime",
)
CORRELATION_PROBE_ENDPOINT = "/api/runtime/health"
STRICT_PRECONDITION_ENDPOINTS = (
    "/health",
    "/api/runtime/health",
    "/api/runtime/readiness",
    "/api/runtime/liveness",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    endpoint: str
    ok: bool
    status_code: int | None
    elapsed_ms: int
    detail: str | None = None


def _normalizar_base_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise ValueError("base-url deve iniciar com http:// ou https://")
    return base


def _fetch(
    base_url: str,
    endpoint: str,
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
) -> tuple[int | None, bytes, dict[str, str], int, str | None]:
    url = f"{base_url}{endpoint}"
    started = time.perf_counter()
    request_headers = {
        "Accept": "application/json, text/html, text/plain",
        "User-Agent": "reqsys-observability-e2e/1.0",
    }
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read(512_000)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            return int(response.status), raw, dict(response.headers.items()), elapsed_ms, None
    except HTTPError as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        body = exc.read(512_000) if exc.fp else b""
        return int(exc.code), body, dict(exc.headers.items()) if exc.headers else {}, elapsed_ms, str(exc)
    except (TimeoutError, URLError, OSError) as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return None, b"", {}, elapsed_ms, f"{type(exc).__name__}: {exc}"


def _check_strict_precondition(base_url: str, timeout: float) -> list[CheckResult]:
    results: list[CheckResult] = []
    for endpoint in STRICT_PRECONDITION_ENDPOINTS:
        status_code, _raw, _headers, elapsed_ms, error = _fetch(base_url, endpoint, timeout=timeout)
        ok = status_code is not None and 200 <= status_code < 300
        results.append(
            CheckResult(
                check_id="strict_precondition",
                endpoint=endpoint,
                ok=ok,
                status_code=status_code,
                elapsed_ms=elapsed_ms,
                detail=error,
            )
        )
    return results


def _check_metrics(base_url: str, timeout: float) -> CheckResult:
    status_code, raw, headers, elapsed_ms, error = _fetch(base_url, "/api/runtime/metrics", timeout=timeout)
    content_type = headers.get("content-type", "")
    body = raw.decode("utf-8", errors="ignore")
    ok = (
        status_code is not None
        and 200 <= status_code < 300
        and "text/plain" in content_type
        and "reqsys_" in body
    )
    detail = error
    if not ok and not detail:
        detail = f"content_type={content_type!r}, reqsys_marker={'reqsys_' in body}"
    return CheckResult("metrics_text_plain", "/api/runtime/metrics", ok, status_code, elapsed_ms, detail)


def _check_dashboard(base_url: str, timeout: float) -> CheckResult:
    status_code, raw, _headers, elapsed_ms, error = _fetch(base_url, "/api/runtime/dashboard", timeout=timeout)
    detail = error
    ok = False
    if status_code is not None and 200 <= status_code < 300:
        try:
            payload = json.loads(raw.decode("utf-8"))
            data = payload.get("data") if isinstance(payload, dict) else None
            ok = (
                isinstance(data, dict)
                and "observability_readiness" in data
                and "correlation_id" in data
                and isinstance(data.get("cards"), list)
            )
            if not ok:
                detail = "payload sem observability_readiness/correlation_id/cards"
        except json.JSONDecodeError:
            detail = "resposta não é JSON válido"
    return CheckResult("dashboard_schema", "/api/runtime/dashboard", ok, status_code, elapsed_ms, detail)


def _check_analytics(base_url: str, timeout: float) -> CheckResult:
    status_code, raw, _headers, elapsed_ms, error = _fetch(base_url, "/api/runtime/analytics", timeout=timeout)
    detail = error
    ok = False
    if status_code is not None and 200 <= status_code < 300:
        try:
            payload = json.loads(raw.decode("utf-8"))
            data = payload.get("data") if isinstance(payload, dict) else None
            telemetry = data.get("operational_telemetry") if isinstance(data, dict) else None
            ok = isinstance(telemetry, dict) and "correlation_id" in telemetry
            if not ok:
                detail = "payload sem data.operational_telemetry.correlation_id"
        except json.JSONDecodeError:
            detail = "resposta não é JSON válido"
    return CheckResult("analytics_telemetry", "/api/runtime/analytics", ok, status_code, elapsed_ms, detail)


def _check_runtime_page(base_url: str, timeout: float) -> CheckResult:
    status_code, raw, _headers, elapsed_ms, error = _fetch(base_url, "/runtime", timeout=timeout)
    body = raw.decode("utf-8", errors="ignore")
    ok = (
        status_code is not None
        and 200 <= status_code < 300
        and "ReqSys Runtime Operational Page" in body
    )
    detail = error
    if not ok and not detail:
        detail = "página /runtime sem marcador operacional esperado"
    return CheckResult("runtime_page", "/runtime", ok, status_code, elapsed_ms, detail)


def _check_correlation_propagation(base_url: str, timeout: float) -> CheckResult:
    correlation_id = f"obs-e2e-{uuid.uuid4().hex[:12]}"
    status_code, raw, headers, elapsed_ms, error = _fetch(
        base_url,
        CORRELATION_PROBE_ENDPOINT,
        timeout=timeout,
        headers={"X-Correlation-ID": correlation_id},
    )
    detail = error
    ok = False
    if status_code is not None and 200 <= status_code < 300:
        header_ok = headers.get("X-Correlation-Id") == correlation_id or headers.get("x-correlation-id") == correlation_id
        try:
            payload = json.loads(raw.decode("utf-8"))
            meta = payload.get("meta") if isinstance(payload, dict) else None
            body_ok = isinstance(meta, dict) and meta.get("correlation_id") == correlation_id
            ok = header_ok and body_ok
            if not ok:
                detail = f"header_ok={header_ok}, body_ok={body_ok}"
        except json.JSONDecodeError:
            detail = "resposta não é JSON válido"
    return CheckResult(
        "correlation_propagation",
        CORRELATION_PROBE_ENDPOINT,
        ok,
        status_code,
        elapsed_ms,
        detail,
    )


def build_payload(
    base_url: str,
    environment: str,
    checks: list[CheckResult],
    *,
    precondition_ok: bool,
) -> dict[str, Any]:
    observability_checks = [c for c in checks if c.check_id != "strict_precondition"]
    ok_count = sum(1 for c in observability_checks if c.ok)
    total = len(observability_checks)
    blocking = [
        f"{check.check_id}@{check.endpoint}: {check.status_code or 'no-http'} {check.detail or ''}".strip()
        for check in observability_checks
        if not check.ok
    ]
    if not precondition_ok:
        blocking.insert(
            0,
            "strict_precondition: Public Runtime Evidence Gate strict ainda não verde (fly_runtime_deploy_lag)",
        )
    return {
        "schema_version": "1.0.0",
        "contract": "observability-e2e-validation",
        "environment": environment,
        "base_url": base_url,
        "validated_at_epoch": int(time.time()),
        "precondition_ok": precondition_ok,
        "total": total,
        "ok": ok_count,
        "failed": total - ok_count,
        "success_percentual": round(ok_count / total * 100, 2) if total else 0.0,
        "gate_passed": precondition_ok and ok_count == total and total > 0,
        "blocking_issues": blocking,
        "checks": [asdict(check) for check in checks],
        "endpoints": list(OBSERVABILITY_E2E_ENDPOINTS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida observabilidade runtime pública (E2E read-only)")
    parser.add_argument("--base-url", default="https://reqsys-api.fly.dev")
    parser.add_argument("--environment", default="prod")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--skip-precondition", action="store_true")
    parser.add_argument("--output", default="artifacts/runtime/observability-e2e-validation.json")
    args = parser.parse_args()

    base_url = _normalizar_base_url(args.base_url)
    checks: list[CheckResult] = []
    precondition_ok = True
    if not args.skip_precondition:
        precondition_checks = _check_strict_precondition(base_url, args.timeout)
        checks.extend(precondition_checks)
        precondition_ok = all(check.ok for check in precondition_checks)

    if precondition_ok or args.skip_precondition:
        checks.extend(
            [
                _check_metrics(base_url, args.timeout),
                _check_dashboard(base_url, args.timeout),
                _check_analytics(base_url, args.timeout),
                _check_runtime_page(base_url, args.timeout),
                _check_correlation_propagation(base_url, args.timeout),
            ]
        )

    payload = build_payload(base_url, args.environment, checks, precondition_ok=precondition_ok)
    output_path = args.output
    from pathlib import Path

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
