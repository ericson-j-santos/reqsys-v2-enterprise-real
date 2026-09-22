#!/usr/bin/env python3
"""Smoke Runtime Executive static publication pair.

Validates that runtime-executive.html and runtime-executive-index.json are
published together as a static pair and that the page points to the exact local
contract expected in public runtime/artifact consumption.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("docs/ops-dashboard")
HTML_NAME = "runtime-executive.html"
CONTRACT_RELATIVE = "./data/runtime-executive-index.json"
CONTRACT_PATH = Path("data/runtime-executive-index.json")
REQUIRED_CONTRACT_LINK_KEYS = {
    "runtime_executive_page",
    "runtime_executive_index",
    "ops_dashboard",
}
FORBIDDEN_RUNTIME_SNIPPETS = {
    "api.github.com",
    "GITHUB_TOKEN",
    "Authorization",
    "github.com/repos",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(f"contrato ausente: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"contrato JSON invalido: {path}: {exc}") from exc


def assert_contains(content: str, needle: str, label: str) -> None:
    if needle not in content:
        raise AssertionError(f"{label} não contém trecho obrigatório: {needle}")


def assert_not_contains(content: str, needle: str, label: str) -> None:
    if needle in content:
        raise AssertionError(f"{label} contém trecho proibido: {needle}")


def validate_html(root: Path) -> str:
    html_path = root / HTML_NAME
    if not html_path.exists():
        raise AssertionError(f"pagina ausente: {html_path}")
    html = html_path.read_text(encoding="utf-8")

    for required in (
        "ReqSys Runtime Executive",
        CONTRACT_RELATIVE,
        "fetch(CONTRACT_URL",
        "runtime-executive-cards",
        "runtime-executive-links",
        "runtime-executive-details",
        "no_runtime_github_api_call",
    ):
        assert_contains(html, required, str(html_path))

    for forbidden in FORBIDDEN_RUNTIME_SNIPPETS:
        assert_not_contains(html, forbidden, str(html_path))

    match = re.search(r"const\s+CONTRACT_URL\s*=\s*['\"]([^'\"]+)['\"]", html)
    if not match:
        raise AssertionError("CONTRACT_URL não encontrado na página")
    contract_url = match.group(1)
    if contract_url != CONTRACT_RELATIVE:
        raise AssertionError(f"CONTRACT_URL divergente: esperado={CONTRACT_RELATIVE}; atual={contract_url}")
    return contract_url


def validate_contract(root: Path) -> dict[str, Any]:
    contract = load_json(root / CONTRACT_PATH)
    summary = contract.get("summary") or {}
    links = contract.get("links") or {}
    public_surfaces = contract.get("public_surfaces") or {}
    guardrails = set(contract.get("guardrails") or [])

    if summary.get("runtime_executive_page_published") is not True:
        raise AssertionError("runtime_executive_page_published deve ser true")

    missing_links = sorted(REQUIRED_CONTRACT_LINK_KEYS - set(links))
    if missing_links:
        raise AssertionError(f"contrato sem links obrigatórios: {missing_links}")

    page_surface = public_surfaces.get("runtime_executive_page") or {}
    if page_surface.get("status") not in {"published", "official"}:
        raise AssertionError("public_surfaces.runtime_executive_page.status deve ser published/official")

    for required_guardrail in {"no_runtime_github_api_call", "official_runtime_executive_deeplink"}:
        if required_guardrail not in guardrails:
            raise AssertionError(f"guardrail ausente: {required_guardrail}")

    return contract


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke Runtime Executive static publication")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Static publication root, e.g. docs/ops-dashboard or artifacts/ops-dashboard")
    parser.add_argument("--output", default="artifacts/runtime-executive-public-smoke/runtime-executive-public-smoke.json")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"raiz de publicação ausente: {root}")

    contract_url = validate_html(root)
    contract = validate_contract(root)

    result = {
        "status": "passed",
        "root": str(root),
        "html": str(root / HTML_NAME),
        "contract": str(root / CONTRACT_PATH),
        "contract_url": contract_url,
        "runtime_executive_score": (contract.get("summary") or {}).get("executive_score"),
        "runtime_executive_risk": (contract.get("summary") or {}).get("risk"),
        "guardrails": contract.get("guardrails") or [],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("runtime executive public smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
