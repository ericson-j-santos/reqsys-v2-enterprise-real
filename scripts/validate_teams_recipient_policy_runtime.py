#!/usr/bin/env python3
"""Avalia, sem mutação, a prontidão do endpoint dinâmico de destinatários Teams."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DYNAMIC_PATH = "/v1/teams-gateway/recipient-policies/{politica}/messages"
LEGACY_PATH = "/v1/teams-gateway/messages"
DEFAULT_BASE_URL = "https://reqsys-api.fly.dev"


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def fetch_openapi(base_url: str, timeout: float) -> dict[str, Any]:
    request = Request(
        f"{base_url.rstrip('/')}/openapi.json",
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "reqsys-teams-runtime-readiness/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"openapi_http_{exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"openapi_network_error: {exc}") from exc

    try:
        document = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"openapi_json_invalid: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        raise RuntimeError("openapi_contract_invalid: paths ausente")
    return document


def evaluate_paths(paths: dict[str, Any]) -> dict[str, Any]:
    dynamic_available = DYNAMIC_PATH in paths
    legacy_available = LEGACY_PATH in paths
    if dynamic_available and legacy_available:
        migration_state = "dynamic_ready"
        result = "passed"
    elif legacy_available:
        migration_state = "legacy_fallback_required"
        result = "advisory"
    else:
        migration_state = "gateway_route_unavailable"
        result = "failed"
    return {
        "dynamic_path": DYNAMIC_PATH,
        "legacy_path": LEGACY_PATH,
        "dynamic_available": dynamic_available,
        "legacy_available": legacy_available,
        "migration_state": migration_state,
        "result": result,
    }


def build_report(base_url: str, document: dict[str, Any], generated_at: datetime | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evaluation = evaluate_paths(document["paths"])
    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "contract": "reqsys-teams-recipient-policy-runtime-readiness",
        "base_url": base_url.rstrip("/"),
        "generated_at": generated_at.isoformat(),
        **evaluation,
        "fallback_contract": {
            "allowed_only_when": "dynamic_endpoint_http_404_and_explicit_destination_configured",
            "masks_auth_or_network_errors": False,
        },
        "production_touched": False,
    }
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    report["evidence_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return report


def execute(base_url: str, output: Path, timeout: float) -> dict[str, Any]:
    document = fetch_openapi(base_url, timeout)
    report = build_report(base_url, document)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--output",
        default="artifacts/teams/recipient-policy-runtime-readiness.json",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--strict-dynamic",
        action="store_true",
        help="Falha enquanto o endpoint dinâmico ainda depender do fallback legado.",
    )
    args = parser.parse_args()
    output = Path(args.output)
    try:
        report = execute(args.base_url, output, args.timeout)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        failure = {
            "schema_version": "1.0.0",
            "contract": "reqsys-teams-recipient-policy-runtime-readiness",
            "base_url": args.base_url.rstrip("/"),
            "generated_at": utc_now().isoformat(),
            "migration_state": "runtime_unreadable",
            "result": "failed",
            "error": str(exc),
            "production_touched": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "result": report["result"],
                "migration_state": report["migration_state"],
                "dynamic_available": report["dynamic_available"],
                "legacy_available": report["legacy_available"],
            },
            ensure_ascii=False,
        )
    )
    if report["result"] == "failed":
        return 1
    if args.strict_dynamic and report["migration_state"] != "dynamic_ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
