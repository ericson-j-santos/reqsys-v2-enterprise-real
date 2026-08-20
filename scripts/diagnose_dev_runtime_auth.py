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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
            "User-Agent": "ReqSysDevRuntimeAuthDiagnostics/1.0",
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
        return {
            "ok": False,
            "status_code": None,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "correlation_id": None,
            "error": type(exc).__name__,
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


def diagnose(repo_root: Path, attempts: int, timeout_seconds: float, interval_seconds: float) -> dict[str, Any]:
    static_state = load_static_fly_state(repo_root)
    probes: dict[str, list[dict[str, Any]]] = {name: [] for name in TARGETS}

    for attempt in range(1, attempts + 1):
        with ThreadPoolExecutor(max_workers=len(TARGETS)) as executor:
            futures = {
                executor.submit(probe_url, name, url, timeout_seconds): name
                for name, url in TARGETS.items()
            }
            for future in as_completed(futures):
                probes[futures[future]].append(future.result())
        if attempt < attempts and interval_seconds > 0:
            time.sleep(interval_seconds)

    aggregate = aggregate_probes(probes, attempts)
    auth_samples = [row.get("auth") for row in probes["auth_config"] if row.get("ok") and row.get("auth")]
    auth = auth_samples[-1] if auth_samples else {}
    classification = classify(aggregate, auth, static_state)

    return {
        "schema_version": "1.0.0",
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
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if args.attempts < 1 or args.attempts > 50:
        parser.error("--attempts deve estar entre 1 e 50")

    repo_root = Path(__file__).resolve().parents[1]
    payload = diagnose(repo_root, args.attempts, args.timeout_seconds, args.interval_seconds)
    output = repo_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": payload["classification"]["status"],
        "operational_risk": payload["classification"]["operational_risk"],
        "suspected_causes": payload["classification"]["suspected_causes"],
        "production_touched": False,
        "evidence": str(output.relative_to(repo_root)),
    }, ensure_ascii=False))

    if args.strict and payload["classification"]["status"] != "ready":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
