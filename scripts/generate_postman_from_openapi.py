#!/usr/bin/env python3
"""Gera coleção Postman v2.1 a partir do contrato OpenAPI ReqSys.

Escopo Lane A — sem dependências externas; cobre paths governados para Newman smoke.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def _load_contract(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("OpenAPI root must be a JSON object")
    return payload


def _operation_requests(path: str, path_item: dict[str, Any], base_url: str) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for method in ("get", "post", "put", "patch", "delete"):
        operation = path_item.get(method)
        if not isinstance(operation, dict):
            continue
        operation_id = operation.get("operationId") or f"{method}_{path.strip('/').replace('/', '_')}"
        url_path = path.replace("{id}", "REQ-001")
        item: dict[str, Any] = {
            "name": f"{method.upper()} {path}",
            "request": {
                "method": method.upper(),
                "header": [{"key": "X-Correlation-ID", "value": "reqsys-postman-smoke", "type": "text"}],
                "url": {
                    "raw": "{{baseUrl}}" + url_path,
                    "host": ["{{baseUrl}}"],
                    "path": [segment for segment in url_path.strip("/").split("/") if segment],
                },
            },
            "response": [],
        }
        if method == "post" and path == "/api/requisitos":
            item["request"]["header"].append({"key": "Content-Type", "value": "application/json"})
            item["request"]["body"] = {
                "mode": "raw",
                "raw": json.dumps(
                    {
                        "titulo": "Smoke Newman ReqSys",
                        "descricao": "Payload mínimo para validação CI report-only.",
                        "tipo": "funcional",
                        "prioridade": "media",
                        "origem": "newman_ci",
                        "metadata": {"versao_contrato": "0.3.0", "correlation_id": "newman-smoke-0001"},
                    },
                    ensure_ascii=False,
                ),
            }
        requests.append({"name": operation_id, **item})
    return requests


def build_collection(contract: dict[str, Any], source: str) -> dict[str, Any]:
    paths = contract.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI paths missing")

    governed_prefixes = ("/api/runtime/", "/api/requisitos", "/health")
    folders: list[dict[str, Any]] = []
    for path, path_item in sorted(paths.items()):
        if not isinstance(path_item, dict):
            continue
        if not any(path.startswith(prefix) or path == prefix for prefix in governed_prefixes):
            continue
        folders.append(
            {
                "name": path,
                "item": _operation_requests(path, path_item, "{{baseUrl}}"),
            }
        )

    info = contract.get("info") if isinstance(contract.get("info"), dict) else {}
    return {
        "info": {
            "name": "ReqSys Runtime OpenAPI (generated)",
            "description": "Coleção gerada do contrato governado para smoke Newman CI.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "_postman_id": "reqsys-openapi-generated",
            "version": info.get("version", "0.3.0"),
        },
        "variable": [
            {"key": "baseUrl", "value": "http://127.0.0.1:8765"},
        ],
        "item": folders,
        "event": [
            {
                "listen": "prerequest",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        f"// generated_at_epoch={int(time.time())}",
                        f"// source={source}",
                    ],
                },
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera Postman collection a partir do OpenAPI ReqSys")
    parser.add_argument(
        "--contract",
        default="docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json",
    )
    parser.add_argument(
        "--output",
        default="docs/integrations/openapi/reqsys-runtime-postman.collection.json",
    )
    args = parser.parse_args()

    contract_path = Path(args.contract)
    collection = build_collection(_load_contract(contract_path), str(contract_path))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "generated", "output": str(output_path), "folders": len(collection["item"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
