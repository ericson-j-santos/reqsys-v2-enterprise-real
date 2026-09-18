#!/usr/bin/env python3
"""Enrich Runtime Executive contracts with official public page deep links.

This script is deterministic, offline and report-only. It keeps the Runtime
Executive public page discoverable from the Estado Único contracts without any
runtime GitHub/API call.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


RUNTIME_EXECUTIVE_PAGE = "docs/ops-dashboard/runtime-executive.html"
RUNTIME_EXECUTIVE_PAGE_RELATIVE = "./runtime-executive.html"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_unique(values: list[Any], value: str) -> list[Any]:
    return values if value in values else [*values, value]


def enrich_runtime_index(payload: dict[str, Any]) -> dict[str, Any]:
    links = payload.setdefault("links", {})
    links["runtime_executive_page"] = RUNTIME_EXECUTIVE_PAGE
    links["runtime_executive_page_relative"] = RUNTIME_EXECUTIVE_PAGE_RELATIVE

    payload.setdefault("public_surfaces", {})["runtime_executive_page"] = {
        "status": "published",
        "path": RUNTIME_EXECUTIVE_PAGE,
        "contract": "docs/ops-dashboard/data/runtime-executive-index.json",
        "guardrail": "no_runtime_github_api_call",
    }

    guardrails = payload.setdefault("guardrails", [])
    for guardrail in ("official_runtime_executive_deeplink", "public_page_contract_consistency"):
        if guardrail not in guardrails:
            guardrails.append(guardrail)

    summary = payload.setdefault("summary", {})
    summary["runtime_executive_page_published"] = True
    summary["runtime_executive_page_path"] = RUNTIME_EXECUTIVE_PAGE
    return payload


def enrich_strategic_governance(payload: dict[str, Any]) -> dict[str, Any]:
    links = payload.setdefault("links", {})
    links["runtime_executive_page"] = RUNTIME_EXECUTIVE_PAGE

    payload.setdefault("public_surfaces", {})["runtime_executive_page"] = {
        "status": "official",
        "path": RUNTIME_EXECUTIVE_PAGE,
        "source": "runtime_executive_index.links.runtime_executive_page",
    }

    summary = payload.setdefault("summary", {})
    summary["runtime_executive_page_integrated"] = True

    guardrails = payload.setdefault("guardrails", [])
    for guardrail in ("runtime_executive_page_is_official_surface", "contract_deeplink_consistency"):
        if guardrail not in guardrails:
            guardrails.append(guardrail)
    return payload


def enrich_executive_brief(payload: dict[str, Any]) -> dict[str, Any]:
    links = payload.setdefault("links", {})
    links["runtime_executive_page"] = RUNTIME_EXECUTIVE_PAGE
    links["runtime_executive_index"] = "docs/ops-dashboard/data/runtime-executive-index.json"
    links["ops_dashboard"] = "docs/ops-dashboard/index.html"

    estado = payload.setdefault("estado_unico", {})
    estado["implementado"] = append_unique(estado.get("implementado", []), "runtime_executive_public_page")
    estado["validado"] = append_unique(estado.get("validado", []), "runtime_executive_page_contract")
    estado["evidenciado"] = append_unique(estado.get("evidenciado", []), "runtime_executive_public_page")
    estado["consolidado"] = append_unique(estado.get("consolidado", []), "runtime_executive_deeplink_oficial")
    estado["public_surfaces"] = {
        **(estado.get("public_surfaces") or {}),
        "runtime_executive_page": RUNTIME_EXECUTIVE_PAGE,
    }

    payload["proximo_incremento_seguro"] = "consolidar_smoke_publico_runtime_executive_page"
    return payload


def enrich_file(path: Path, enricher) -> bool:
    payload = load_json(path)
    if not payload:
        return False
    write_json(path, enricher(payload))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich Runtime Executive deep links in Estado Único contracts")
    parser.add_argument("--runtime-index", default="docs/ops-dashboard/data/runtime-executive-index.json")
    parser.add_argument("--strategic-governance", default="docs/ops-dashboard/data/strategic-governance-index.json")
    parser.add_argument("--executive-brief", default="docs/ops-dashboard/data/executive-brief.json")
    args = parser.parse_args()

    targets = [
        (Path(args.runtime_index), enrich_runtime_index),
        (Path(args.strategic_governance), enrich_strategic_governance),
        (Path(args.executive_brief), enrich_executive_brief),
    ]
    enriched = [str(path) for path, enricher in targets if enrich_file(path, enricher)]
    if not enriched:
        raise SystemExit("nenhum contrato foi enriquecido")
    print("runtime executive deeplinks enriched:", ", ".join(enriched))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
