#!/usr/bin/env python3
"""Valida endpoints públicos mínimos do ReqSys no Fly.

Uso:
    python scripts/validate_public_runtime.py --base-url https://reqsys-api.fly.dev

A validação é read-only, não envia credenciais e não depende de bibliotecas externas.
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


DEFAULT_ENDPOINTS = (
    "/",
    "/health",
    "/api/runtime/health",
    "/api/runtime/readiness",
    "/api/runtime/liveness",
    "/api/runtime/metrics",
    "/api/runtime/dashboard",
)


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


def validar_endpoint(base_url: str, endpoint: str, timeout: float) -> EndpointResult:
    url = f"{base_url}{endpoint}"
    started = time.perf_counter()
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "reqsys-runtime-smoke/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL fornecida explicitamente pelo operador
            raw = response.read(512_000)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            _payload, payload_keys = _ler_json_seguro(raw)
            return EndpointResult(
                endpoint=endpoint,
                url=url,
                ok=200 <= int(response.status) < 300,
                status_code=int(response.status),
                elapsed_ms=elapsed_ms,
                content_type=response.headers.get("content-type"),
                payload_keys=payload_keys,
            )
    except HTTPError as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return EndpointResult(
            endpoint=endpoint,
            url=url,
            ok=False,
            status_code=int(exc.code),
            elapsed_ms=elapsed_ms,
            content_type=exc.headers.get("content-type") if exc.headers else None,
            error=str(exc),
        )
    except (TimeoutError, URLError, OSError) as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return EndpointResult(
            endpoint=endpoint,
            url=url,
            ok=False,
            status_code=None,
            elapsed_ms=elapsed_ms,
            content_type=None,
            error=f"{type(exc).__name__}: {exc}",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida smoke público do ReqSys no Fly")
    parser.add_argument("--base-url", default="https://reqsys-api.fly.dev", help="URL base pública da API")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout por endpoint em segundos")
    parser.add_argument("--endpoint", action="append", dest="endpoints", help="Endpoint adicional ou substituto; pode repetir")
    parser.add_argument("--output", default="public-runtime-validation.json", help="Arquivo JSON de evidência")
    args = parser.parse_args()

    base_url = _normalizar_base_url(args.base_url)
    endpoints = tuple(args.endpoints) if args.endpoints else DEFAULT_ENDPOINTS
    results = [validar_endpoint(base_url, endpoint, args.timeout) for endpoint in endpoints]
    ok_count = sum(1 for result in results if result.ok)
    payload = {
        "schema_version": "1.0.0",
        "base_url": base_url,
        "validated_at_epoch": int(time.time()),
        "total": len(results),
        "ok": ok_count,
        "failed": len(results) - ok_count,
        "success_percentual": round((ok_count / len(results) * 100), 2) if results else 0.0,
        "results": [asdict(result) for result in results],
    }

    with open(args.output, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
