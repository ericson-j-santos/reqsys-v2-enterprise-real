#!/usr/bin/env python3
"""Validate all configured ReqSys environments in read-only mode.

The validator emits an evidence artifact for development, test, staging and
production without requiring every external endpoint to be green. CI should fail
only for contract/build errors, while operational degradation is captured inside
JSON for dashboards and governance decisions.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class EnvironmentTarget:
    name: str
    frontend: str
    api: str
    notes: str


ENVIRONMENTS = [
    EnvironmentTarget(
        name="desenvolvimento",
        frontend="https://reqsys-app-dev.fly.dev",
        api="https://reqsys-api-dev.fly.dev/docs",
        notes="Fly dev; local usa docker-compose.yml + docker-compose.dev.yml",
    ),
    EnvironmentTarget(
        name="testes",
        frontend="http://localhost:8084",
        api="http://localhost:8212/docs",
        notes="Docker test",
    ),
    EnvironmentTarget(
        name="homologacao",
        frontend="https://reqsys-web-stg.fly.dev",
        api="https://reqsys-api-stg.fly.dev",
        notes="Fly staging",
    ),
    EnvironmentTarget(
        name="producao",
        frontend="https://reqsys-app.fly.dev",
        api="https://reqsys-api.fly.dev/docs",
        notes="Fly producao; local usa docker-compose.yml + docker-compose.prod.yml",
    ),
]


def is_local_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0"}


def probe_url(url: str, timeout_seconds: float, skip_local: bool = True) -> dict[str, Any]:
    if skip_local and is_local_url(url):
        return {
            "url": url,
            "ok": False,
            "status_code": None,
            "elapsed_ms": 0,
            "content_type": None,
            "mode": "local_skipped",
            "error": "local endpoint skipped in CI/read-only validation",
        }

    started = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": "ReqSysEnvironmentValidator/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            status_code = int(getattr(response, "status", 0) or 0)
            return {
                "url": url,
                "ok": 200 <= status_code < 400,
                "status_code": status_code,
                "elapsed_ms": elapsed_ms,
                "content_type": response.headers.get("content-type"),
                "mode": "remote_probe",
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "url": url,
            "ok": False,
            "status_code": exc.code,
            "elapsed_ms": elapsed_ms,
            "content_type": exc.headers.get("content-type") if exc.headers else None,
            "mode": "remote_probe",
            "error": f"HTTP Error {exc.code}: {exc.reason}",
        }
    except Exception as exc:  # noqa: BLE001 - report-only validator must capture all probe errors
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "url": url,
            "ok": False,
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "content_type": None,
            "mode": "remote_probe",
            "error": str(exc),
        }


def classify_environment(frontend_probe: dict[str, Any], api_probe: dict[str, Any]) -> dict[str, Any]:
    checks = [frontend_probe, api_probe]
    remote_checks = [item for item in checks if item.get("mode") != "local_skipped"]
    ok_count = sum(1 for item in checks if item.get("ok"))
    skipped_count = sum(1 for item in checks if item.get("mode") == "local_skipped")
    readiness_percent = round((ok_count / len(checks)) * 100, 2)

    if skipped_count == len(checks):
        status = "local_only"
        risk = "medium"
    elif remote_checks and all(item.get("ok") for item in remote_checks):
        status = "ready"
        risk = "low"
    elif ok_count > 0:
        status = "degraded"
        risk = "medium"
    else:
        status = "unavailable"
        risk = "high"

    return {
        "status": status,
        "operational_risk": risk,
        "readiness_percent": readiness_percent,
        "ok_checks": ok_count,
        "total_checks": len(checks),
        "skipped_checks": skipped_count,
    }


def validate_all_environments(timeout_seconds: float = 5.0, skip_local: bool = True) -> dict[str, Any]:
    environments: list[dict[str, Any]] = []
    for target in ENVIRONMENTS:
        frontend_probe = probe_url(target.frontend, timeout_seconds, skip_local=skip_local)
        api_probe = probe_url(target.api, timeout_seconds, skip_local=skip_local)
        classification = classify_environment(frontend_probe, api_probe)
        environments.append(
            {
                "name": target.name,
                "frontend": target.frontend,
                "api": target.api,
                "notes": target.notes,
                **classification,
                "checks": {
                    "frontend": frontend_probe,
                    "api": api_probe,
                },
            }
        )

    ready_count = sum(1 for item in environments if item["status"] == "ready")
    degraded_count = sum(1 for item in environments if item["status"] == "degraded")
    unavailable_count = sum(1 for item in environments if item["status"] == "unavailable")
    local_only_count = sum(1 for item in environments if item["status"] == "local_only")
    average_readiness = round(sum(item["readiness_percent"] for item in environments) / len(environments), 2)
    overall_status = "ready" if ready_count == len(environments) else "degraded" if ready_count or degraded_count or local_only_count else "unavailable"

    return {
        "schema_version": "1.0.0",
        "contract": "all-environments-readiness-validation",
        "generated_at_epoch": int(time.time()),
        "summary": {
            "overall_status": overall_status,
            "average_readiness_percent": average_readiness,
            "environments_total": len(environments),
            "ready": ready_count,
            "degraded": degraded_count,
            "unavailable": unavailable_count,
            "local_only": local_only_count,
            "mode": "read_only_non_blocking",
        },
        "environments": environments,
        "guardrails": [
            "read_only_probe",
            "non_blocking_operational_evidence",
            "no_secret_required",
            "local_endpoints_skipped_by_default",
            "ci_should_fail_only_on_contract_errors",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate all ReqSys environments")
    parser.add_argument("--output", default="docs/ops-dashboard/data/environments-validation.json")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--probe-local", action="store_true", help="Probe localhost targets instead of marking them as local_only")
    args = parser.parse_args()

    payload = validate_all_environments(timeout_seconds=args.timeout_seconds, skip_local=not args.probe_local)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
