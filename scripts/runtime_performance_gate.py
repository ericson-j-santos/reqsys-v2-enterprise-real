#!/usr/bin/env python3
"""
Gate dinâmico de performance HTTP do ReqSys.

Mede, por endpoint público:
- p50/p95/p99 de latência;
- throughput;
- taxa de erro;
- conformidade com orçamento versionado.

Sem dependências externas.

Uso:
    python scripts/runtime_performance_gate.py \
      --base-url https://reqsys-api.fly.dev \
      --budgets config/runtime-performance-budgets.json \
      --output artifacts/performance/runtime-performance.json \
      --strict
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

VERSION = "1.0.0"
USER_AGENT = f"ReqSys-Runtime-Performance-Gate/{VERSION}"


@dataclass(frozen=True)
class Sample:
    ok: bool
    status_code: int | None
    elapsed_ms: float
    error: str | None


def percentile(values: Iterable[float], q: float) -> float:
    ordered = sorted(float(v) for v in values)
    if not ordered:
        return 0.0
    if not 0 <= q <= 1:
        raise ValueError("percentile q deve estar entre 0 e 1")
    if len(ordered) == 1:
        return round(ordered[0], 2)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 2)
    weight = position - lower
    value = ordered[lower] * (1 - weight) + ordered[upper] * weight
    return round(value, 2)


def _request_once(
    url: str,
    *,
    timeout_seconds: float,
    expected_status: int,
    headers: dict[str, str] | None = None,
) -> Sample:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "X-Correlation-Id": str(uuid.uuid4()),
    }
    if headers:
        request_headers.update(headers)

    request = Request(url=url, method="GET", headers=request_headers)
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response.read(1024)
            elapsed_ms = (time.perf_counter() - started) * 1000
            status = int(response.status)
            return Sample(
                ok=status == expected_status,
                status_code=status,
                elapsed_ms=round(elapsed_ms, 2),
                error=None if status == expected_status else f"HTTP inesperado: {status}",
            )
    except HTTPError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return Sample(
            ok=False,
            status_code=int(exc.code),
            elapsed_ms=round(elapsed_ms, 2),
            error=f"HTTPError: {exc.code}",
        )
    except (URLError, TimeoutError, OSError) as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return Sample(
            ok=False,
            status_code=None,
            elapsed_ms=round(elapsed_ms, 2),
            error=f"{type(exc).__name__}: {exc}",
        )


def evaluate_budget(metrics: dict[str, float], budget: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    checks = (
        ("p95_ms", "max_p95_ms", "<="),
        ("p99_ms", "max_p99_ms", "<="),
        ("error_rate_percent", "max_error_rate_percent", "<="),
        ("throughput_rps", "min_throughput_rps", ">="),
    )
    for metric_key, budget_key, operator in checks:
        if budget_key not in budget:
            continue
        actual = float(metrics.get(metric_key, 0.0))
        target = float(budget[budget_key])
        violated = actual > target if operator == "<=" else actual < target
        if violated:
            violations.append(
                f"{metric_key}={actual:.2f} viola {budget_key}={target:.2f}"
            )
    return violations


def _validate_endpoint_config(endpoint: dict[str, Any]) -> None:
    required = ("name", "path", "expected_status", "budget")
    missing = [key for key in required if key not in endpoint]
    if missing:
        raise ValueError(f"Endpoint sem campos obrigatórios: {', '.join(missing)}")
    method = str(endpoint.get("method", "GET")).upper()
    if method != "GET":
        raise ValueError(
            f"Gate dinâmico só aceita GET por segurança; endpoint {endpoint['name']} usa {method}"
        )
    if not str(endpoint["path"]).startswith("/"):
        raise ValueError(f"path deve iniciar com '/': {endpoint['path']}")


def run_endpoint(
    *,
    base_url: str,
    endpoint: dict[str, Any],
    defaults: dict[str, Any],
    samples_override: int | None = None,
    concurrency_override: int | None = None,
) -> dict[str, Any]:
    _validate_endpoint_config(endpoint)

    samples = int(samples_override or endpoint.get("samples") or defaults.get("samples", 20))
    concurrency = int(
        concurrency_override
        or endpoint.get("concurrency")
        or defaults.get("concurrency", 4)
    )
    timeout_seconds = float(
        endpoint.get("timeout_seconds") or defaults.get("timeout_seconds", 5)
    )
    warmup = int(endpoint.get("warmup") or defaults.get("warmup", 3))

    if samples < 1:
        raise ValueError("samples deve ser >= 1")
    if concurrency < 1:
        raise ValueError("concurrency deve ser >= 1")
    concurrency = min(concurrency, samples)

    url = urljoin(base_url.rstrip("/") + "/", str(endpoint["path"]).lstrip("/"))
    expected_status = int(endpoint["expected_status"])

    for _ in range(max(0, warmup)):
        _request_once(
            url,
            timeout_seconds=timeout_seconds,
            expected_status=expected_status,
        )

    measured: list[Sample] = []
    wall_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                _request_once,
                url,
                timeout_seconds=timeout_seconds,
                expected_status=expected_status,
            )
            for _ in range(samples)
        ]
        for future in as_completed(futures):
            measured.append(future.result())
    wall_seconds = max(time.perf_counter() - wall_started, 0.000001)

    latencies = [item.elapsed_ms for item in measured]
    success_count = sum(1 for item in measured if item.ok)
    failed_count = len(measured) - success_count
    metrics = {
        "samples": len(measured),
        "success": success_count,
        "failed": failed_count,
        "error_rate_percent": round((failed_count / len(measured)) * 100, 2)
        if measured
        else 100.0,
        "throughput_rps": round(success_count / wall_seconds, 2),
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "p99_ms": percentile(latencies, 0.99),
        "avg_ms": round(statistics.fmean(latencies), 2) if latencies else 0.0,
        "max_ms": round(max(latencies), 2) if latencies else 0.0,
        "wall_seconds": round(wall_seconds, 3),
    }

    budget = dict(endpoint["budget"])
    violations = evaluate_budget(metrics, budget)
    errors = sorted({item.error for item in measured if item.error})

    return {
        "name": endpoint["name"],
        "method": "GET",
        "path": endpoint["path"],
        "url": url,
        "expected_status": expected_status,
        "budget": budget,
        "metrics": metrics,
        "violations": violations,
        "errors": errors[:10],
        "status": "passed" if not violations else "blocked",
    }


def load_policy(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0.0":
        raise ValueError("schema_version de performance não suportada")
    endpoints = payload.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError("policy precisa conter endpoints")
    for endpoint in endpoints:
        _validate_endpoint_config(endpoint)
    return payload


def build_report(
    *,
    base_url: str,
    policy: dict[str, Any],
    results: list[dict[str, Any]],
    strict: bool,
) -> dict[str, Any]:
    blocked = [item for item in results if item["status"] == "blocked"]
    return {
        "schema_version": "1.0.0",
        "gate_version": VERSION,
        "contract": "reqsys-runtime-performance-budget",
        "base_url": base_url.rstrip("/"),
        "strict": strict,
        "policy_version": policy.get("policy_version", "unknown"),
        "generated_at_epoch": int(time.time()),
        "summary": {
            "status": "blocked" if blocked else "passed",
            "endpoints_total": len(results),
            "endpoints_passed": len(results) - len(blocked),
            "endpoints_blocked": len(blocked),
        },
        "results": results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ReqSys runtime performance gate")
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--budgets",
        default="config/runtime-performance-budgets.json",
        type=Path,
    )
    parser.add_argument(
        "--output",
        default="artifacts/performance/runtime-performance.json",
        type=Path,
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        policy = load_policy(args.budgets)
        defaults = dict(policy.get("defaults", {}))
        results = [
            run_endpoint(
                base_url=args.base_url,
                endpoint=endpoint,
                defaults=defaults,
                samples_override=args.samples,
                concurrency_override=args.concurrency,
            )
            for endpoint in policy["endpoints"]
        ]
        report = build_report(
            base_url=args.base_url,
            policy=policy,
            results=results,
            strict=args.strict,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report["summary"], ensure_ascii=False))
        blocked = report["summary"]["endpoints_blocked"]
        return 1 if args.strict and blocked else 0
    except Exception as exc:
        print(f"runtime_performance_gate_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
