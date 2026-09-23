#!/usr/bin/env python3
"""Validate ReqSys development environment in read-only mode.

This validator emits a dedicated development-environment evidence artifact without
requiring the public dev endpoints to be green. CI should fail only for contract
or serialization errors; operational degradation is represented inside JSON for
Ops Dashboard / Strategic Governance decisions.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class DevTarget:
    name: str
    frontend: str
    api_docs: str
    api_health: str
    notes: str


def build_dev_target(base_url: str) -> DevTarget:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("REQSYS_DEV_BASE_URL_missing")
    parsed = urlparse(base)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise ValueError("REQSYS_DEV_BASE_URL_invalid")
    if host.endswith(".fly.dev"):
        raise ValueError("legacy_fly_dev_runtime_forbidden")
    return DevTarget(
        name="desenvolvimento",
        frontend=base,
        api_docs=base + "/api/docs",
        api_health=base + "/api/health",
        notes="PC24x7 DEV via locator assinado; validação pública read-only sem secrets",
    )


def is_public_https_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc) and parsed.hostname not in {"localhost", "127.0.0.1", "0.0.0.0"}


def probe_url(url: str, timeout_seconds: float) -> dict[str, Any]:
    started = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": "ReqSysDevEnvironmentValidator/1.0"})
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
    except Exception as exc:  # noqa: BLE001 - report-only validator must capture every probe failure
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


def classify_dev_environment(checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total_checks = len(checks)
    ok_count = sum(1 for probe in checks.values() if probe.get("ok"))
    readiness_percent = round((ok_count / total_checks) * 100, 2)

    if ok_count == total_checks:
        status = "ready"
        risk = "low"
        recommended_action = "manter_monitoramento"
    elif ok_count > 0:
        status = "degraded"
        risk = "medium"
        recommended_action = "validar_endpoints_dev_pendentes"
    else:
        status = "unavailable"
        risk = "high"
        recommended_action = "corrigir_publicacao_dev_ou_dns"

    return {
        "status": status,
        "operational_risk": risk,
        "readiness_percent": readiness_percent,
        "ok_checks": ok_count,
        "total_checks": total_checks,
        "recommended_action": recommended_action,
    }


def validate_dev_environment(timeout_seconds: float = 5.0, base_url: str | None = None) -> dict[str, Any]:
    target = build_dev_target(base_url or os.getenv("REQSYS_DEV_BASE_URL", ""))
    urls = {
        "frontend": target.frontend,
        "api_docs": target.api_docs,
        "api_health": target.api_health,
    }
    invalid_urls = [name for name, url in urls.items() if not is_public_https_url(url)]
    if invalid_urls:
        raise ValueError(f"invalid public HTTPS target(s): {', '.join(invalid_urls)}")

    checks = {name: probe_url(url, timeout_seconds) for name, url in urls.items()}
    classification = classify_dev_environment(checks)

    return {
        "schema_version": "1.0.0",
        "contract": "dev-environment-readiness-validation",
        "generated_at_epoch": int(time.time()),
        "environment": {
            "name": target.name,
            "frontend": target.frontend,
            "api_docs": target.api_docs,
            "api_health": target.api_health,
            "notes": target.notes,
            **classification,
            "checks": checks,
        },
        "summary": {
            "overall_status": classification["status"],
            "readiness_percent": classification["readiness_percent"],
            "operational_risk": classification["operational_risk"],
            "recommended_action": classification["recommended_action"],
            "mode": "read_only_non_blocking",
        },
        "guardrails": [
            "read_only_probe",
            "non_blocking_operational_evidence",
            "no_secret_required",
            "public_https_targets_only",
            "ci_should_fail_only_on_contract_errors",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ReqSys development environment")
    parser.add_argument("--output", default="docs/ops-dashboard/data/dev-environments-validation.json")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--dev-base-url", default=os.getenv("REQSYS_DEV_BASE_URL", ""))
    args = parser.parse_args()

    payload = validate_dev_environment(timeout_seconds=args.timeout_seconds, base_url=args.dev_base_url)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
