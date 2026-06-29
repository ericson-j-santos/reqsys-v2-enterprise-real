#!/usr/bin/env python3
"""Diff semântico OpenAPI ↔ rotas FastAPI do backend.

Compara paths e métodos HTTP do contrato OpenAPI com rotas estáticas
extraídas de backend/app/api/*.py (sem subir a aplicação).

Escopo P2 — report-only (advisory). Gate bloqueante canonico: validate_openapi_routes_drift.py.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import time
from pathlib import Path
from typing import Any

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})
ROUTE_DECORATOR_RE = re.compile(r"^@(\w+)\.(get|post|put|patch|delete|head|options)\(")


def _normalize_path(path: str) -> str:
    normalized = path.strip() or "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    normalized = re.sub(r"/+", "/", normalized)
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return re.sub(r"\{[^}]+\}", "{param}", normalized)


def _literal_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_router_prefixes(tree: ast.AST) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if not (isinstance(func, ast.Name) and func.id == "APIRouter"):
            continue
        prefix = ""
        for keyword in node.value.keywords:
            if keyword.arg == "prefix":
                prefix = _literal_str(keyword.value) or ""
        prefixes[node.targets[0].id] = prefix
    return prefixes


def _extract_routes_from_file(path: Path) -> set[tuple[str, str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    prefixes = _extract_router_prefixes(tree)
    routes: set[tuple[str, str]] = set()

    for index, line in enumerate(source.splitlines()):
        match = ROUTE_DECORATOR_RE.match(line.strip())
        if not match:
            continue
        router_name, method = match.group(1), match.group(2).upper()
        prefix = prefixes.get(router_name, "")
        route_path = ""
        arg_match = re.search(
            rf"@{re.escape(router_name)}\.{method.lower()}\(\s*['\"]([^'\"]*)['\"]",
            line,
        )
        if arg_match:
            route_path = arg_match.group(1)
        else:
            continuation = "\n".join(source.splitlines()[index : index + 4])
            multiline = re.search(
                rf"@{re.escape(router_name)}\.{method.lower()}\(\s*\n\s*['\"]([^'\"]*)['\"]",
                continuation,
            )
            if multiline:
                route_path = multiline.group(1)
        full_path = _normalize_path(f"{prefix}{route_path}")
        routes.add((method, full_path))

    return routes


def extract_backend_routes(api_dir: Path) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    if not api_dir.exists():
        return routes
    for path in sorted(api_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        routes.update(_extract_routes_from_file(path))
    return routes


def extract_openapi_routes(contract: dict[str, Any]) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    paths = contract.get("paths")
    if not isinstance(paths, dict):
        return routes
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        normalized_path = _normalize_path(path)
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            if isinstance(operation, dict):
                routes.add((method.upper(), normalized_path))
    return routes


def _path_matches(openapi_path: str, backend_path: str) -> bool:
    if openapi_path == backend_path:
        return True
    openapi_parts = openapi_path.strip("/").split("/")
    backend_parts = backend_path.strip("/").split("/")
    if len(openapi_parts) != len(backend_parts):
        return False
    for openapi_part, backend_part in zip(openapi_parts, backend_parts, strict=True):
        if openapi_part == "{param}" or backend_part == "{param}":
            continue
        if openapi_part != backend_part:
            return False
    return True


def _find_backend_route(
    method: str,
    openapi_path: str,
    backend_routes: set[tuple[str, str]],
) -> tuple[str, str] | None:
    for backend_method, backend_path in backend_routes:
        if backend_method == method and _path_matches(openapi_path, backend_path):
            return backend_method, backend_path
    return None


def build_semantic_diff(
    contract_path: Path,
    api_dir: Path,
    *,
    scope: str = "contract_paths",
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {
            "schema_version": "1.0.0",
            "contract": "reqsys-openapi-semantic-diff",
            "validated_at_epoch": int(time.time()),
            "source": str(contract_path),
            "status": "failed",
            "errors": [f"json_parse_failed: {exc}"],
            "drifts": [],
            "summary": {
                "drift_count": 0,
                "openapi_routes": 0,
                "backend_routes": 0,
                "missing_in_backend": 0,
                "missing_in_openapi": 0,
                "method_mismatches": 0,
            },
        }

    openapi_routes = extract_openapi_routes(contract)
    backend_routes = extract_backend_routes(api_dir)
    drifts: list[dict[str, str]] = []

    openapi_targets = sorted(openapi_routes)
    if scope == "runtime_contract":
        runtime_prefixes = ("/api/runtime/", "/api/requisitos")
        openapi_targets = [
            item for item in openapi_routes if item[1].startswith(runtime_prefixes)
        ]

    matched_backend: set[tuple[str, str]] = set()
    for method, openapi_path in openapi_targets:
        backend_match = _find_backend_route(method, openapi_path, backend_routes)
        if backend_match is None:
            drifts.append(
                {
                    "code": "missing_in_backend",
                    "severity": "high",
                    "method": method,
                    "openapi_path": openapi_path,
                    "detail": f"Contrato OpenAPI define {method} {openapi_path} sem rota backend correspondente",
                }
            )
        else:
            matched_backend.add(backend_match)

    if scope in {"contract_paths", "runtime_contract"}:
        backend_targets = sorted(backend_routes)
        if scope == "runtime_contract":
            runtime_prefixes = ("/api/runtime/", "/api/requisitos")
            backend_targets = [
                item for item in backend_routes if item[1].startswith(runtime_prefixes)
            ]
        for method, backend_path in backend_targets:
            if backend_path in {m[1] for m in matched_backend}:
                continue
            openapi_match = _find_backend_route(method, backend_path, openapi_routes)
            if openapi_match is None:
                drifts.append(
                    {
                        "code": "missing_in_openapi",
                        "severity": "medium",
                        "method": method,
                        "backend_path": backend_path,
                        "detail": f"Rota backend {method} {backend_path} ausente no contrato OpenAPI",
                    }
                )

    summary = {
        "drift_count": len(drifts),
        "openapi_routes": len(openapi_routes),
        "backend_routes": len(backend_routes),
        "missing_in_backend": sum(1 for item in drifts if item["code"] == "missing_in_backend"),
        "missing_in_openapi": sum(1 for item in drifts if item["code"] == "missing_in_openapi"),
        "method_mismatches": sum(1 for item in drifts if item["code"] == "method_mismatch"),
        "scope": scope,
    }
    status = "passed" if summary["drift_count"] == 0 else "drift_detected"
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-openapi-semantic-diff",
        "validated_at_epoch": int(time.time()),
        "source": str(contract_path),
        "backend_api_dir": str(api_dir),
        "status": status,
        "errors": errors,
        "drifts": drifts,
        "summary": summary,
        "guardrails": [
            "static_ast_route_extraction",
            "no_runtime_import",
            "report_only_by_default",
            "path_param_normalization",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff semântico OpenAPI ↔ backend FastAPI")
    parser.add_argument(
        "--contract",
        default="docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json",
        help="Caminho do contrato OpenAPI JSON",
    )
    parser.add_argument(
        "--api-dir",
        default="backend/app/api",
        help="Diretório com módulos FastAPI",
    )
    parser.add_argument(
        "--output",
        default="artifacts/openapi/openapi-semantic-diff.json",
        help="Caminho do artifact de diff",
    )
    parser.add_argument(
        "--scope",
        choices=["contract_paths", "runtime_contract", "all"],
        default="runtime_contract",
        help="Escopo do diff semântico",
    )
    args = parser.parse_args()

    report = build_semantic_diff(Path(args.contract), Path(args.api_dir), scope=args.scope)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["status"] == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
