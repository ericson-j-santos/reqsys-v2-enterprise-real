#!/usr/bin/env python3
"""Diagnóstico read-only da disponibilidade e autenticação do ReqSys DEV.

Executa probes públicos repetidos, compara o runtime com a configuração Fly
versionada e produz somente evidência sanitizada. Nenhum secret, tenant id,
client id, token, UPN ou corpo arbitrário de resposta é persistido.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import tomllib
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any


TARGETS = {
    "frontend": "https://reqsys-app-dev.fly.dev/",
    "health": "https://reqsys-api-dev.fly.dev/health",
    "runtime_health": "https://reqsys-api-dev.fly.dev/api/runtime/health",
    "readiness": "https://reqsys-api-dev.fly.dev/api/runtime/readiness",
    "liveness": "https://reqsys-api-dev.fly.dev/api/runtime/liveness",
    "auth_config": "https://reqsys-api-dev.fly.dev/v1/auth/config",
}

SAFE_AUTH_FIELDS = (
    "azure_enabled",
    "certificate_enabled",
    "demo_login_enabled",
    "environment",
    "auth_status",
    "missing_fields",
    "expected_redirect_uri",
)

TIMEOUT_ERRORS = {
    "TimeoutError",
    "socket.timeout",
    "diagnostic_wall_clock_timeout",
}


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def sanitize_auth_payload(payload: Any) -> dict[str, Any]:
    """Mantém apenas metadados públicos necessários ao diagnóstico."""
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return {}
    return {key: data.get(key) for key in SAFE_AUTH_FIELDS if key in data}


def load_static_fly_state(repo_root: Path) -> dict[str, Any]:
    backend_path = repo_root / "backend" / "fly.dev.toml"
    frontend_path = repo_root / "frontend" / "fly.dev.toml"

    with backend_path.open("rb") as handle:
        backend = tomllib.load(handle)
    with frontend_path.open("rb") as handle:
        frontend = tomllib.load(handle)

    backend_http = backend.get("http_service", {})
    frontend_http = frontend.get("http_service", {})
    backend_env = backend.get("env", {})

    return {
        "backend": {
            "app": backend.get("app"),
            "auto_stop_machines": backend_http.get("auto_stop_machines"),
            "auto_start_machines": backend_http.get("auto_start_machines"),
            "min_machines_running": backend_http.get("min_machines_running"),
            "allow_demo_login_declared": str(backend_env.get("ALLOW_DEMO_LOGIN", "")).lower() == "true",
            "public_environment_declared": backend_env.get("PUBLIC_ENVIRONMENT"),
        },
        "frontend": {
            "app": frontend.get("app"),
            "auto_stop_machines": frontend_http.get("auto_stop_machines"),
            "auto_start_machines": frontend_http.get("auto_start_machines"),
            "min_machines_running": frontend_http.get("min_machines_running"),
        },
    }


def probe_url(name: str, url: str, timeout_seconds: float) -> dict[str, Any]:
    started = time.perf_counter()
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ReqSysDevRuntimeAuthDiagnostics/1.1",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            status_code = int(getattr(response, "status", 0) or 0)
            result: dict[str, Any] = {
                "ok": 200 <= status_code < 400,
                "status_code": status_code,
                "elapsed_ms": elapsed_ms,
                "correlation_id": response.headers.get("x-correlation-id")
                or response.headers.get("x-request-id"),
                "error": None,
            }
            if name == "auth_config" and result["ok"]:
                raw = response.read(65536)
                try:
                    result["auth"] = sanitize_auth_payload(json.loads(raw.decode("utf-8")))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    result["auth"] = {}
                    result["error"] = "auth_config_invalid_json"
                    result["ok"] = False
            return result
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status_code": exc.code,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "correlation_id": exc.headers.get("x-correlation-id") if exc.headers else None,
            "error": f"http_{exc.code}",
        }
    except Exception as exc:  # noqa: BLE001 - evidência deve capturar falhas operacionais
        error_name = "TimeoutError" if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower() else type(exc).__name__
        return {
            "ok": False,
            "status_code": None,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "correlation_id": None,
            "error": error_name,
        }


def aggregate_probes(probes: dict[str, list[dict[str, Any]]], attempts: int) -> dict[str, Any]:
    aggregate: dict[str, Any] = {}
    for name, rows in probes.items():
        elapsed = [int(row["elapsed_ms"]) for row in rows]
        statuses = sorted({row.get("status_code") for row in rows if row.get("status_code") is not None})
        success_count = sum(1 for row in rows if row.get("ok"))
        aggregate[name] = {
            "attempts": attempts,
            "success_count": success_count,
            "failure_count": attempts - success_count,
            "success_rate_percent": round((success_count / attempts) * 100, 2),
            "status_codes": statuses,
            "latency_ms": {
                "min": min(elapsed) if elapsed else None,
                "p50": _percentile(elapsed, 0.50),
                "p95": _percentile(elapsed, 0.95),
                "max": max(elapsed) if elapsed else None,
            },
            "errors": sorted({row.get("error") for row in rows if row.get("error")}),
            "correlation_ids": sorted({row.get("correlation_id") for row in rows if row.get("correlation_id")}),
        }
    return aggregate


def classify(aggregate: dict[str, Any], auth: dict[str, Any], static_state: dict[str, Any]) -> dict[str, Any]:
    suspected_causes: list[str] = []
    critical_targets = ("frontend", "health", "runtime_health", "readiness", "liveness")

    intermittent = any(0 < aggregate[name]["success_count"] < aggregate[name]["attempts"] for name in critical_targets)
    unavailable = any(aggregate[name]["success_count"] == 0 for name in critical_targets)
    if intermittent:
        suspected_causes.append("runtime_or_network_intermitency")
    if unavailable:
        suspected_causes.append("runtime_endpoint_unavailable")

    backend_min = static_state["backend"].get("min_machines_running")
    frontend_min = static_state["frontend"].get("min_machines_running")
    min_running_ok = backend_min is not None and backend_min >= 1 and frontend_min is not None and frontend_min >= 1
    if not min_running_ok:
        suspected_causes.append("cold_start_configuration_risk")

    auth_available = bool(
        auth.get("azure_enabled")
        or auth.get("certificate_enabled")
        or auth.get("demo_login_enabled")
    )
    if auth and not auth_available:
        suspected_causes.append("all_login_methods_disabled_at_runtime")

    demo_expected = bool(static_state["backend"].get("allow_demo_login_declared")) and str(
        static_state["backend"].get("public_environment_declared") or ""
    ).lower() not in {"production", "producao"}
    if auth and demo_expected and not auth.get("demo_login_enabled"):
        suspected_causes.append("runtime_configuration_drift_demo_login")

    missing_fields = auth.get("missing_fields") or []
    if auth and not auth.get("azure_enabled") and missing_fields:
        suspected_causes.append("azure_runtime_configuration_missing")

    fully_stable = all(aggregate[name]["failure_count"] == 0 for name in critical_targets)
    if fully_stable and auth_available:
        status = "ready"
        risk = "low"
    elif unavailable or not auth_available:
        status = "degraded"
        risk = "high"
    else:
        status = "degraded"
        risk = "medium"

    return {
        "status": status,
        "operational_risk": risk,
        "auth_available": auth_available,
        "minimum_running_configuration_ok": min_running_ok,
        "suspected_causes": suspected_causes,
        "production_touched": False,
    }


def build_performance_summary(
    probes: dict[str, list[dict[str, Any]]],
    aggregate: dict[str, Any],
    round_metrics: list[dict[str, Any]],
    total_duration_ms: int,
    budget_seconds: float,
    warning_seconds: float,
    budget_exceeded: bool,
) -> dict[str, Any]:
    all_elapsed = [
        int(row["elapsed_ms"])
        for rows in probes.values()
        for row in rows
        if row.get("elapsed_ms") is not None
    ]
    timeout_count = sum(
        1
        for rows in probes.values()
        for row in rows
        if row.get("error") in TIMEOUT_ERRORS
    )

    slowest_round = max(round_metrics, key=lambda row: row["duration_ms"]) if round_metrics else None

    endpoint_candidates = [
        (name, data["latency_ms"].get("p95"))
        for name, data in aggregate.items()
        if data.get("latency_ms", {}).get("p95") is not None
    ]
    if endpoint_candidates:
        slowest_endpoint_name, slowest_endpoint_p95 = max(endpoint_candidates, key=lambda item: int(item[1]))
        slowest_endpoint = {
            "name": slowest_endpoint_name,
            "p95_ms": int(slowest_endpoint_p95),
        }
    else:
        slowest_endpoint = None

    budget_ms = int(budget_seconds * 1000)
    warning_ms = int(warning_seconds * 1000)
    if budget_exceeded or total_duration_ms > budget_ms:
        status = "red"
        alert_code = "diagnostic_wall_clock_timeout"
    elif total_duration_ms > warning_ms:
        status = "yellow"
        alert_code = "diagnostic_slow_warning"
    else:
        status = "green"
        alert_code = None

    return {
        "status": status,
        "alert_code": alert_code,
        "total_duration_ms": total_duration_ms,
        "overall_p95_ms": _percentile(all_elapsed, 0.95),
        "timeout_count": timeout_count,
        "budget_seconds": budget_seconds,
        "warning_seconds": warning_seconds,
        "budget_exceeded": budget_exceeded,
        "slowest_round": slowest_round,
        "slowest_endpoint": slowest_endpoint,
        "rounds": round_metrics,
    }


def apply_performance_classification(
    classification: dict[str, Any],
    performance: dict[str, Any],
) -> dict[str, Any]:
    result = dict(classification)
    causes = list(result.get("suspected_causes") or [])
    result["diagnostic_performance"] = performance["status"]

    if performance["status"] == "yellow":
        if "diagnostic_slow_warning" not in causes:
            causes.append("diagnostic_slow_warning")
        if result.get("operational_risk") == "low":
            result["operational_risk"] = "medium"
    elif performance["status"] == "red":
        if "diagnostic_wall_clock_timeout" not in causes:
            causes.append("diagnostic_wall_clock_timeout")
        result["status"] = "degraded"
        result["operational_risk"] = "high"

    result["suspected_causes"] = causes
    return result


def _wall_clock_timeout_row(attempt: int) -> dict[str, Any]:
    return {
        "ok": False,
        "status_code": None,
        "elapsed_ms": 0,
        "correlation_id": None,
        "error": "diagnostic_wall_clock_timeout",
        "attempt": attempt,
    }


def diagnose(
    repo_root: Path,
    attempts: int,
    timeout_seconds: float,
    interval_seconds: float,
    budget_seconds: float = 60.0,
    warning_seconds: float = 30.0,
) -> dict[str, Any]:
    static_state = load_static_fly_state(repo_root)
    probes: dict[str, list[dict[str, Any]]] = {name: [] for name in TARGETS}
    round_metrics: list[dict[str, Any]] = []
    diagnostic_started = time.perf_counter()
    deadline = diagnostic_started + budget_seconds
    budget_exceeded = False

    for attempt in range(1, attempts + 1):
        round_started = time.perf_counter()
        remaining_seconds = deadline - round_started

        if remaining_seconds <= 0:
            budget_exceeded = True
            for skipped_attempt in range(attempt, attempts + 1):
                for name in TARGETS:
                    probes[name].append(_wall_clock_timeout_row(skipped_attempt))
            break

        request_timeout = min(timeout_seconds, max(0.1, remaining_seconds))
        executor = ThreadPoolExecutor(max_workers=len(TARGETS))
        futures = {
            executor.submit(probe_url, name, url, request_timeout): name
            for name, url in TARGETS.items()
        }
        done, not_done = wait(futures, timeout=max(0.0, remaining_seconds))

        for future in done:
            name = futures[future]
            result = future.result()
            result["attempt"] = attempt
            probes[name].append(result)

        if not_done:
            budget_exceeded = True
            for future in not_done:
                name = futures[future]
                future.cancel()
                probes[name].append(_wall_clock_timeout_row(attempt))

        executor.shutdown(wait=False, cancel_futures=True)

        round_duration_ms = int((time.perf_counter() - round_started) * 1000)
        round_metrics.append(
            {
                "attempt": attempt,
                "duration_ms": round_duration_ms,
                "budget_remaining_ms": max(0, int((deadline - time.perf_counter()) * 1000)),
            }
        )

        if budget_exceeded:
            for skipped_attempt in range(attempt + 1, attempts + 1):
                for name in TARGETS:
                    probes[name].append(_wall_clock_timeout_row(skipped_attempt))
            break

        if attempt < attempts and interval_seconds > 0:
            sleep_seconds = min(interval_seconds, max(0.0, deadline - time.perf_counter()))
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    total_duration_ms = int((time.perf_counter() - diagnostic_started) * 1000)
    if total_duration_ms > int(budget_seconds * 1000):
        budget_exceeded = True

    aggregate = aggregate_probes(probes, attempts)
    auth_samples = [row.get("auth") for row in probes["auth_config"] if row.get("ok") and row.get("auth")]
    auth = auth_samples[-1] if auth_samples else {}

    performance = build_performance_summary(
        probes=probes,
        aggregate=aggregate,
        round_metrics=round_metrics,
        total_duration_ms=total_duration_ms,
        budget_seconds=budget_seconds,
        warning_seconds=warning_seconds,
        budget_exceeded=budget_exceeded,
    )
    classification = apply_performance_classification(
        classify(aggregate, auth, static_state),
        performance,
    )

    return {
        "schema_version": "1.1.0",
        "contract": "dev-runtime-auth-diagnostics",
        "correlation_id": str(uuid.uuid4()),
        "generated_at_epoch": int(time.time()),
        "environment": "development",
        "attempts_per_target": attempts,
        "timeout_seconds": timeout_seconds,
        "targets": TARGETS,
        "static_fly_configuration": static_state,
        "runtime_auth": auth,
        "probe_summary": aggregate,
        "performance": performance,
        "classification": classification,
        "guardrails": {
            "read_only": True,
            "secrets_collected": False,
            "personal_identity_collected": False,
            "production_touched": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnosticar runtime/autenticação DEV do ReqSys")
    parser.add_argument("--output", default="artifacts/dev-runtime-auth-diagnostics/evidence.json")
    parser.add_argument("--attempts", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--interval-seconds", type=float, default=0.5)
    parser.add_argument("--budget-seconds", type=float, default=60.0)
    parser.add_argument("--warning-seconds", type=float, default=30.0)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if args.attempts < 1 or args.attempts > 50:
        parser.error("--attempts deve estar entre 1 e 50")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds deve ser maior que zero")
    if args.interval_seconds < 0:
        parser.error("--interval-seconds não pode ser negativo")
    if args.warning_seconds <= 0:
        parser.error("--warning-seconds deve ser maior que zero")
    if args.budget_seconds <= args.warning_seconds:
        parser.error("--budget-seconds deve ser maior que --warning-seconds")

    repo_root = Path(__file__).resolve().parents[1]
    payload = diagnose(
        repo_root,
        args.attempts,
        args.timeout_seconds,
        args.interval_seconds,
        args.budget_seconds,
        args.warning_seconds,
    )
    output = repo_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": payload["classification"]["status"],
        "operational_risk": payload["classification"]["operational_risk"],
        "diagnostic_performance": payload["performance"]["status"],
        "diagnostic_duration_ms": payload["performance"]["total_duration_ms"],
        "suspected_causes": payload["classification"]["suspected_causes"],
        "production_touched": False,
        "evidence": str(output.relative_to(repo_root)),
    }, ensure_ascii=False))

    if payload["performance"]["status"] == "red":
        return 3
    if args.strict and payload["classification"]["status"] != "ready":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
