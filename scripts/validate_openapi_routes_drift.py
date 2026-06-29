#!/usr/bin/env python3
"""Detecta drift entre rotas FastAPI governadas e contrato OpenAPI ReqSys.

Escopo Lane C — report-only; não altera backend nem contrato.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

CANONICAL_DRIFT_ARTIFACT = "artifacts/openapi/openapi-routes-drift.json"
CANONICAL_DRIFT_CONTRACT = "reqsys-openapi-routes-drift"


def contract_drift_count(report: dict[str, Any] | None) -> int:
    """Contagem canônica de drift para gates strict (Lane C)."""
    if not report:
        return 0
    summary = report.get("summary") or {}
    missing = int(summary.get("missing_in_openapi") or 0) + int(summary.get("missing_in_backend") or 0)
    if missing > 0:
        return missing
    if report.get("status") not in {None, "passed"}:
        return max(len(report.get("errors") or []), 1)
    return 0


GOVERNED_PATHS: tuple[tuple[str, str], ...] = (
    ("GET", "/api/runtime/health"),
    ("GET", "/api/runtime/dashboard"),
    ("GET", "/api/runtime/analytics"),
    ("GET", "/api/requisitos"),
    ("GET", "/api/requisitos/{id}"),
    ("POST", "/api/requisitos"),
)


def _normalize_path(path: str) -> str:
    normalized = path.rstrip("/") or "/"
    return re.sub(r"\{[^}]+\}", "{param}", normalized)


def _display_path(normalized_path: str) -> str:
    return normalized_path


def _collect_fastapi_routes() -> set[tuple[str, str]]:
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("DATABASE_URL", "sqlite:///./reqsys.db")
    os.environ.setdefault("JWT_SECRET", "ci-placeholder-secret-min-32-chars-long")
    os.environ.setdefault("JWT_ISSUER", "reqsys-ci")
    os.environ.setdefault("JWT_AUDIENCE", "reqsys-ci")

    from app.main import app  # noqa: PLC0415

    schema = app.openapi()
    paths = schema.get("paths")
    if not isinstance(paths, dict):
        return set()

    operations: set[tuple[str, str]] = set()
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        normalized = _normalize_path(path)
        for method in ("get", "post", "put", "patch", "delete"):
            if method in path_item:
                operations.add((method.upper(), normalized))
    return operations


def _collect_openapi_operations(contract: dict[str, Any]) -> set[tuple[str, str]]:
    paths = contract.get("paths")
    if not isinstance(paths, dict):
        return set()
    operations: set[tuple[str, str]] = set()
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        normalized = _normalize_path(path)
        for method in ("get", "post", "put", "patch", "delete"):
            if method in path_item:
                operations.add((method.upper(), normalized))
    return operations


def _load_contract(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("OpenAPI root must be a JSON object")
    return payload


def analyze_drift(contract_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        contract = _load_contract(contract_path)
    except Exception as exc:  # noqa: BLE001
        return {
            "schema_version": "1.0.0",
            "contract": "reqsys-openapi-routes-drift",
            "validated_at_epoch": int(time.time()),
            "source": str(contract_path),
            "status": "failed",
            "mode": "report-only",
            "errors": [f"contract_load_failed: {exc}"],
            "warnings": [],
            "summary": {"valid": False, "governed_paths": len(GOVERNED_PATHS)},
        }

    try:
        backend_routes = _collect_fastapi_routes()
    except Exception as exc:  # noqa: BLE001
        return {
            "schema_version": "1.0.0",
            "contract": "reqsys-openapi-routes-drift",
            "validated_at_epoch": int(time.time()),
            "source": str(contract_path),
            "status": "failed",
            "mode": "report-only",
            "errors": [f"backend_routes_introspection_failed: {exc}"],
            "warnings": [],
            "summary": {"valid": False, "governed_paths": len(GOVERNED_PATHS)},
        }

    openapi_ops = _collect_openapi_operations(contract)
    backend_normalized = {(method, _normalize_path(path)) for method, path in backend_routes}
    openapi_normalized = {(method, _normalize_path(path)) for method, path in openapi_ops}
    governed_normalized = {(method, _normalize_path(path)) for method, path in GOVERNED_PATHS}

    governed_backend = {item for item in governed_normalized if item in backend_normalized}
    governed_openapi = {item for item in governed_normalized if item in openapi_normalized}

    missing_in_openapi = sorted(governed_backend - openapi_normalized)
    missing_in_backend = sorted(governed_openapi - backend_normalized)
    openapi_only = sorted(
        (method, path)
        for method, path in openapi_normalized
        if path.startswith("/api/runtime/") or path.startswith("/api/requisitos")
        if (method, path) not in backend_normalized
    )

    for method, path in missing_in_openapi:
        errors.append(f"backend_route_missing_in_openapi:{method} {_display_path(path)}")
    for method, path in missing_in_backend:
        errors.append(f"openapi_operation_missing_in_backend:{method} {_display_path(path)}")
    for method, path in openapi_only[:10]:
        warnings.append(f"openapi_operation_not_in_backend:{method} {path}")

    status = "passed" if not errors else "failed"
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-openapi-routes-drift",
        "validated_at_epoch": int(time.time()),
        "source": str(contract_path),
        "status": status,
        "mode": "report-only",
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "valid": status == "passed",
            "governed_paths": len(GOVERNED_PATHS),
            "backend_routes_total": len(backend_routes),
            "openapi_operations_total": len(openapi_ops),
            "governed_backend_matched": len(governed_backend & governed_openapi),
            "missing_in_openapi": len(missing_in_openapi),
            "missing_in_backend": len(missing_in_backend),
        },
        "details": {
            "governed_paths": [{"method": m, "path": p} for m, p in GOVERNED_PATHS],
            "missing_in_openapi": [{"method": m, "path": p} for m, p in missing_in_openapi],
            "missing_in_backend": [{"method": m, "path": p} for m, p in missing_in_backend],
        },
        "guardrails": [
            "report_only",
            "governed_paths_only",
            "no_backend_mutation",
            "ci_artifact_enabled",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detecta drift entre rotas FastAPI e OpenAPI ReqSys")
    parser.add_argument(
        "--contract",
        default="docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json",
    )
    parser.add_argument(
        "--output",
        default="artifacts/openapi/openapi-routes-drift.json",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Retorna exit code 1 quando houver drift (default: report-only sempre 0)",
    )
    args = parser.parse_args()

    report = analyze_drift(Path(args.contract))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.strict and report["status"] != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
