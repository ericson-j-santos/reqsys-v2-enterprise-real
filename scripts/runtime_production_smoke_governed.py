#!/usr/bin/env python3
"""Governed production runtime smoke for ReqSys.

Valida endpoints públicos essenciais do runtime com GETs seguros, retry leve e
artifact JSON rastreável. O gate é intencionalmente pequeno para servir como
confirmação pós-merge/produção sem duplicar pipelines pesadas.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://reqsys-app.fly.dev"
DEFAULT_OUTPUT = "artifacts/runtime-production-smoke-governed.json"

REQUIRED_ENDPOINTS: tuple[tuple[str, int, str], ...] = (
    ("/health", 200, "basic_health"),
    ("/api/runtime/health", 200, "runtime_health"),
    ("/api/runtime/readiness", 200, "traffic_readiness"),
    ("/api/runtime/liveness", 200, "process_liveness"),
)

OPTIONAL_ENDPOINTS: tuple[tuple[str, int, str], ...] = (
    ("/", 200, "public_landing"),
    ("/runtime", 200, "runtime_operational_page"),
    ("/api/runtime/contracts", 200, "runtime_contract"),
    ("/api/runtime/version", 200, "runtime_version"),
    ("/api/runtime/build-info", 200, "runtime_build"),
    ("/api/runtime/dependencies", 200, "runtime_dependencies"),
    ("/api/runtime/evidence/summary", 200, "runtime_evidence_summary"),
    ("/api/requisitos/runtime/inspection", 200, "requisitos_runtime_inspection"),
)


@dataclass(frozen=True)
class EndpointCheck:
    path: str
    purpose: str
    required: bool
    expected_http: int
    actual_http: int | None
    ok: bool
    latency_ms: int | None
    error: str | None = None
    envelope_status: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_base_url(value: str) -> str:
    base = value.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise ValueError("base_url must start with http:// or https://")
    return base


def _decode_envelope_status(body: bytes, content_type: str | None) -> str | None:
    if not body or not content_type or "json" not in content_type.lower():
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            health = data.get("health")
            if isinstance(health, dict) and isinstance(health.get("status"), str):
                return health["status"]
            if isinstance(data.get("status"), str):
                return data["status"]
        if isinstance(payload.get("status"), str):
            return payload["status"]
    return None


def check_endpoint(
    base_url: str,
    path: str,
    *,
    purpose: str,
    expected_http: int,
    required: bool,
    timeout_seconds: float,
    attempts: int,
    delay_seconds: float,
) -> EndpointCheck:
    last_error: str | None = None
    url = f"{base_url}{path}"
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        try:
            request = Request(url, headers={"Accept": "application/json,text/html;q=0.9,*/*;q=0.1"})
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - URL pública configurada
                body = response.read(16_384)
                latency_ms = int((time.monotonic() - started) * 1000)
                status = getattr(response, "status", None) or response.getcode()
                content_type = response.headers.get("content-type") if response.headers else None
                envelope_status = _decode_envelope_status(body, content_type)
                return EndpointCheck(
                    path=path,
                    purpose=purpose,
                    required=required,
                    expected_http=expected_http,
                    actual_http=status,
                    ok=status == expected_http,
                    latency_ms=latency_ms,
                    envelope_status=envelope_status,
                )
        except HTTPError as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            last_error = f"http_{exc.code}"
            if attempt >= attempts:
                return EndpointCheck(path, purpose, required, expected_http, exc.code, False, latency_ms, last_error)
        except (URLError, TimeoutError, OSError) as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            last_error = type(exc).__name__
            if attempt >= attempts:
                return EndpointCheck(path, purpose, required, expected_http, None, False, latency_ms, last_error)
        time.sleep(delay_seconds)
    return EndpointCheck(path, purpose, required, expected_http, None, False, None, last_error or "unknown")


def build_report(
    checks: list[EndpointCheck],
    *,
    base_url: str,
    repository: str | None,
    run_id: str | None,
) -> dict[str, Any]:
    required = [check for check in checks if check.required]
    optional = [check for check in checks if not check.required]
    required_ok = sum(1 for check in required if check.ok)
    optional_ok = sum(1 for check in optional if check.ok)
    total_ok = sum(1 for check in checks if check.ok)
    latencies = [check.latency_ms for check in checks if check.latency_ms is not None]
    required_percent = round((required_ok / len(required)) * 100, 2) if required else 100.0
    total_percent = round((total_ok / len(checks)) * 100, 2) if checks else 100.0
    status = "healthy" if required_ok == len(required) else "degraded"
    return {
        "schema_version": "1.0.0",
        "source": "runtime-production-smoke-governed",
        "status": status,
        "base_url": base_url,
        "validated_at": utc_now(),
        "repository": repository,
        "github_run_id": run_id,
        "required_ok": required_ok,
        "required_total": len(required),
        "optional_ok": optional_ok,
        "optional_total": len(optional),
        "required_success_percentual": required_percent,
        "total_success_percentual": total_percent,
        "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "risk": "low" if status == "healthy" else "high",
        "checks": [asdict(check) for check in checks],
    }


def run_smoke(
    *,
    base_url: str,
    timeout_seconds: float,
    attempts: int,
    delay_seconds: float,
    repository: str | None,
    run_id: str | None,
) -> dict[str, Any]:
    checks: list[EndpointCheck] = []
    for path, expected_http, purpose in REQUIRED_ENDPOINTS:
        checks.append(
            check_endpoint(
                base_url,
                path,
                purpose=purpose,
                expected_http=expected_http,
                required=True,
                timeout_seconds=timeout_seconds,
                attempts=attempts,
                delay_seconds=delay_seconds,
            )
        )
    for path, expected_http, purpose in OPTIONAL_ENDPOINTS:
        checks.append(
            check_endpoint(
                base_url,
                path,
                purpose=purpose,
                expected_http=expected_http,
                required=False,
                timeout_seconds=timeout_seconds,
                attempts=attempts,
                delay_seconds=delay_seconds,
            )
        )
    return build_report(checks, base_url=base_url, repository=repository, run_id=run_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Governed production runtime smoke for ReqSys")
    parser.add_argument("--base-url", default=os.getenv("RUNTIME_PUBLIC_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--github-run-id", default=os.getenv("GITHUB_RUN_ID", ""))
    parser.add_argument("--allow-degraded", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_url = normalize_base_url(args.base_url)
    report = run_smoke(
        base_url=base_url,
        timeout_seconds=args.timeout_seconds,
        attempts=max(1, args.attempts),
        delay_seconds=max(0.0, args.delay_seconds),
        repository=args.repository or None,
        run_id=args.github_run_id or None,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(
            "runtime_production_smoke="
            f"{report['status']} required={report['required_ok']}/{report['required_total']} "
            f"total={report['total_success_percentual']}% output={output}"
        )
    return 0 if report["status"] == "healthy" or args.allow_degraded else 1


if __name__ == "__main__":
    raise SystemExit(main())
