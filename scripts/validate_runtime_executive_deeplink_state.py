#!/usr/bin/env python3
"""Validate Runtime Executive public page deep links across Estado Único contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_EXECUTIVE_PAGE = "docs/ops-dashboard/runtime-executive.html"
LOCAL_LINKS_TO_VALIDATE = {
    "runtime_executive_page",
    "runtime_executive_index",
    "runtime_executive_page_relative",
    "strategic_governance_index",
    "executive_brief",
    "ops_dashboard",
}
EXPECTED_LINKS = {
    "runtime_index": ROOT / "docs" / "ops-dashboard" / "data" / "runtime-executive-index.json",
    "strategic_governance": ROOT / "docs" / "ops-dashboard" / "data" / "strategic-governance-index.json",
    "executive_brief": ROOT / "docs" / "ops-dashboard" / "data" / "executive-brief.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(f"contrato ausente: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def assert_link(payload: dict[str, Any], key: str, expected: str) -> None:
    links = payload.get("links") or {}
    actual = links.get(key)
    if actual != expected:
        raise AssertionError(f"link {key} invalido: esperado={expected!r}; atual={actual!r}")


def resolve_local_link(path_value: str) -> Path:
    if path_value.startswith("./"):
        return ROOT / "docs" / "ops-dashboard" / path_value[2:]
    return ROOT / path_value


def assert_relative_path_exists(path_value: str) -> None:
    if path_value.startswith("http"):
        return
    target = resolve_local_link(path_value)
    if not target.exists():
        raise AssertionError(f"link local aponta para arquivo inexistente: {path_value}")


def validate_runtime_index(payload: dict[str, Any]) -> None:
    assert_link(payload, "runtime_executive_page", RUNTIME_EXECUTIVE_PAGE)
    assert_link(payload, "runtime_executive_page_relative", "./runtime-executive.html")
    public_surface = (payload.get("public_surfaces") or {}).get("runtime_executive_page") or {}
    if public_surface.get("path") != RUNTIME_EXECUTIVE_PAGE:
        raise AssertionError("public_surfaces.runtime_executive_page.path inconsistente")
    if (payload.get("summary") or {}).get("runtime_executive_page_published") is not True:
        raise AssertionError("summary.runtime_executive_page_published deve ser true")


def validate_strategic_governance(payload: dict[str, Any]) -> None:
    assert_link(payload, "runtime_executive_page", RUNTIME_EXECUTIVE_PAGE)
    if (payload.get("summary") or {}).get("runtime_executive_page_integrated") is not True:
        raise AssertionError("summary.runtime_executive_page_integrated deve ser true")


def validate_executive_brief(payload: dict[str, Any]) -> None:
    assert_link(payload, "runtime_executive_page", RUNTIME_EXECUTIVE_PAGE)
    estado = payload.get("estado_unico") or {}
    for bucket, expected in {
        "implementado": "runtime_executive_public_page",
        "validado": "runtime_executive_page_contract",
        "evidenciado": "runtime_executive_public_page",
        "consolidado": "runtime_executive_deeplink_oficial",
    }.items():
        values = estado.get(bucket) or []
        if expected not in values:
            raise AssertionError(f"estado_unico.{bucket} sem {expected}")


def validate_local_links(payload: dict[str, Any]) -> None:
    for key, value in (payload.get("links") or {}).items():
        if key not in LOCAL_LINKS_TO_VALIDATE:
            continue
        if isinstance(value, str) and value:
            assert_relative_path_exists(value)


def main() -> int:
    page = ROOT / RUNTIME_EXECUTIVE_PAGE
    if not page.exists():
        raise SystemExit(f"pagina runtime executive ausente: {page}")

    runtime_index = load_json(EXPECTED_LINKS["runtime_index"])
    strategic = load_json(EXPECTED_LINKS["strategic_governance"])
    brief = load_json(EXPECTED_LINKS["executive_brief"])

    validate_runtime_index(runtime_index)
    validate_strategic_governance(strategic)
    validate_executive_brief(brief)
    for payload in (runtime_index, strategic, brief):
        validate_local_links(payload)

    print("runtime executive deeplink state validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
