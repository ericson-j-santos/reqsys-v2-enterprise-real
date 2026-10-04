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

try:
    from scripts.runtime_url_policy import require_authorized_runtime_url
except ModuleNotFoundError:  # execução direta: python scripts/<arquivo>.py
    from runtime_url_policy import require_authorized_runtime_url


@dataclass(frozen=True)
class EnvironmentTarget:
    name: str
    frontend: str
    api: str
    notes: str
    canonical: str | None = None


def _require_https_url(value: str, *, label: str) -> str:
    url = require_authorized_runtime_url(value, label=label)
    if not url.startswith("https://"):
        raise ValueError(f"{label} deve usar HTTPS")
    return url


def parse_environment_target(value: str) -> EnvironmentTarget:
    canonical, separator, endpoints = value.partition("=")
    frontend, comma, api = endpoints.partition(",")
    canonical = canonical.strip().lower()
    if not separator or not comma or not canonical:
        raise ValueError(
            "--environment deve seguir o formato NOME=FRONTEND_URL,API_URL"
        )
    frontend_url = _require_https_url(
        frontend,
        label=f"frontend do ambiente {canonical}",
    )
    api_url = _require_https_url(api, label=f"API do ambiente {canonical}")
    return EnvironmentTarget(
        name=canonical,
        frontend=frontend_url,
        api=api_url,
        notes="runtime provider-neutral informado explicitamente",
        canonical=canonical,
    )


def _validated_targets(targets: list[EnvironmentTarget]) -> list[EnvironmentTarget]:
    if not targets:
        raise ValueError("ao menos um ambiente deve ser informado explicitamente")
    validated: list[EnvironmentTarget] = []
    for target in targets:
        canonical = (target.canonical or target.name).strip().lower()
        validated.append(
            EnvironmentTarget(
                name=target.name,
                frontend=_require_https_url(
                    target.frontend,
                    label=f"frontend do ambiente {canonical}",
                ),
                api=_require_https_url(
                    target.api,
                    label=f"API do ambiente {canonical}",
                ),
                notes=target.notes,
                canonical=canonical,
            )
        )
    return validated


def is_local_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0"}


def probe_url(url: str, timeout_seconds: float, skip_local: bool = True) -> dict[str, Any]:
    url = _require_https_url(url, label="URL de probe do ambiente")
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
    except Exception as exc:  # noqa: BLE001 - validador report-only registra falhas do probe
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


def validate_all_environments(
    targets: list[EnvironmentTarget],
    timeout_seconds: float = 5.0,
    skip_local: bool = True,
) -> dict[str, Any]:
    targets = _validated_targets(targets)
    environments: list[dict[str, Any]] = []
    for target in targets:
        frontend_probe = probe_url(target.frontend, timeout_seconds, skip_local=skip_local)
        api_probe = probe_url(target.api, timeout_seconds, skip_local=skip_local)
        classification = classify_environment(frontend_probe, api_probe)
        environments.append(
            {
                "name": target.name,
                "canonical": target.canonical,
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
            "explicit_provider_neutral_https_targets",
            "ci_should_fail_only_on_contract_errors",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate all ReqSys environments")
    parser.add_argument("--output", default="docs/ops-dashboard/data/environments-validation.json")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument(
        "--environment",
        action="append",
        required=True,
        metavar="NOME=FRONTEND_URL,API_URL",
        help="Ambiente e URLs HTTPS provider-neutral; repita para cada ambiente.",
    )
    args = parser.parse_args()

    try:
        targets = [parse_environment_target(value) for value in args.environment]
    except ValueError as exc:
        parser.error(str(exc))
    payload = validate_all_environments(
        targets,
        timeout_seconds=args.timeout_seconds,
        skip_local=False,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
