#!/usr/bin/env python3
"""Validate static Ops Dashboard navigation artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "docs/ops-dashboard/operational-navigation-index.json"
HTML_PATH = ROOT / "docs/ops-dashboard/operational-navigation.html"

REQUIRED_LINK_IDS = {
    "ops_dashboard_main",
    "trilha_d_history_dashboard",
    "operational_pareto_dashboard",
    "predictive_regression_dashboard",
    "executive_brief_dashboard",
    "operational_runtime_governance",
    "operational_evidence_hub",
    "runtime_governance_contract",
    "runtime_governance_runbook",
    "runtime_contract_governance_policy",
    "power_platform_runtime_runbook",
}

REQUIRED_DEEP_LINK_HREFS = {
    "trilha_d_history_dashboard": "./index.html#trilha-d-history-card",
    "operational_pareto_dashboard": "./index.html#operational-pareto-card",
    "predictive_regression_dashboard": "./index.html#predictive-regression-card",
}

REQUIRED_ARTIFACT_HREFS = {
    "executive_brief_dashboard": "./data/executive-brief.json",
}

REQUIRED_HTML_TERMS = [
    "ReqSys — Navegação Operacional",
    "operational-navigation-index.json",
    "operational-runtime-governance.html",
    "operational-evidence-hub.html",
    "fallback_navigation",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def validate_index() -> None:
    if not INDEX_PATH.exists():
        fail(f"missing navigation index: {INDEX_PATH.relative_to(ROOT)}")
    payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "0.1.0":
        fail("schema_version must be 0.1.0")
    links = payload.get("links") or []
    ids = {item.get("id") for item in links if isinstance(item, dict)}
    missing = REQUIRED_LINK_IDS - ids
    if missing:
        fail(f"missing required navigation links: {sorted(missing)}")
    by_id = {item.get("id"): item for item in links if isinstance(item, dict)}
    for item in links:
        if not item.get("href") or not item.get("title") or not item.get("category"):
            fail(f"invalid navigation link: {item}")
    for link_id, expected_href in REQUIRED_DEEP_LINK_HREFS.items():
        link = by_id.get(link_id)
        if not link:
            fail(f"missing required navigation link: {link_id}")
        if link.get("href") != expected_href:
            fail(f"unexpected href for {link_id}: {link.get('href')!r} (expected {expected_href!r})")
    for link_id, expected_href in REQUIRED_ARTIFACT_HREFS.items():
        link = by_id.get(link_id)
        if not link:
            fail(f"missing required navigation link: {link_id}")
        if link.get("href") != expected_href:
            fail(f"unexpected href for {link_id}: {link.get('href')!r} (expected {expected_href!r})")


def validate_html() -> None:
    if not HTML_PATH.exists():
        fail(f"missing navigation page: {HTML_PATH.relative_to(ROOT)}")
    text = HTML_PATH.read_text(encoding="utf-8")
    for term in REQUIRED_HTML_TERMS:
        if term not in text:
            fail(f"missing term in navigation page: {term}")


def main() -> int:
    try:
        validate_index()
        validate_html()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "validated": "ops_dashboard_navigation"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
