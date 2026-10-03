#!/usr/bin/env python3
"""Validate dedicated Runtime Executive public page.

The check is deterministic and offline. It guarantees that the public page keeps
using the canonical runtime executive contract without runtime GitHub/API calls.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "ops-dashboard" / "runtime-executive.html"
CONTRACT = ROOT / "docs" / "ops-dashboard" / "data" / "runtime-executive-index.json"


REQUIRED_SNIPPETS = [
    "ReqSys Runtime Executive",
    "./data/runtime-executive-index.json",
    "runtime-executive-cards",
    "runtime-executive-links",
    "runtime-executive-details",
    "fetch(CONTRACT_URL",
    "no_runtime_github_api_call",
]

FORBIDDEN_SNIPPETS = [
    "api.github.com",
    "github.com/repos",
    "GITHUB_TOKEN",
    "Authorization",
]


def main() -> int:
    if not PAGE.exists():
        raise SystemExit(f"pagina runtime executive ausente: {PAGE}")

    if not CONTRACT.exists():
        raise SystemExit(f"contrato runtime executive ausente: {CONTRACT}")

    html = PAGE.read_text(encoding="utf-8")

    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in html]
    if missing:
        raise SystemExit(f"pagina runtime executive sem trechos obrigatorios: {missing}")

    forbidden = [snippet for snippet in FORBIDDEN_SNIPPETS if snippet in html]
    if forbidden:
        raise SystemExit(f"pagina runtime executive contem chamada/segredo proibido: {forbidden}")

    if html.count("<section") < 3:
        raise SystemExit("pagina runtime executive deve ter secoes executivas minimas")

    print("runtime executive public page validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
