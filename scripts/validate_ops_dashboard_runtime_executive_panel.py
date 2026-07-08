#!/usr/bin/env python3
"""Validate Runtime Executive panel wiring in the static Ops Dashboard.

This validator is intentionally offline and read-only. It checks whether the
static HTML exposes the runtime executive index as an actual dashboard panel,
not only as a loose JSON artifact.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_HTML = ROOT / "docs/ops-dashboard/index.html"
RUNTIME_EXECUTIVE_INDEX = ROOT / "docs/ops-dashboard/data/runtime-executive-index.json"

REQUIRED_HTML_TOKENS = {
    "Runtime Executive Index — visão pública consolidada",
    "./data/runtime-executive-index.json",
    "exec-score",
    "exec-risk",
    "exec-readiness",
    "exec-mergeability",
    "runtime-executive-cards",
    "runtime-executive-links",
    "runtime-executive-details",
    "renderRuntimeExecutiveIndex",
}

REQUIRED_INDEX_KEYS = {
    "schema_version",
    "repo",
    "summary",
    "cards",
    "links",
    "guardrails",
}

REQUIRED_INDEX_CARDS = {
    "health",
    "readiness",
    "merge_intelligence",
    "evidence_gate",
    "finalization",
    "runtime_validation",
}

REQUIRED_INDEX_LINKS = {
    "ops_dashboard",
    "runtime_executive_index",
    "executive_brief",
    "runtime_validation_snapshot",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def validate_html() -> None:
    if not DASHBOARD_HTML.exists():
        fail("missing docs/ops-dashboard/index.html")
    html = DASHBOARD_HTML.read_text(encoding="utf-8")
    missing = sorted(token for token in REQUIRED_HTML_TOKENS if token not in html)
    if missing:
        fail(f"dashboard runtime executive panel missing tokens: {missing}")


def validate_index_contract() -> None:
    if not RUNTIME_EXECUTIVE_INDEX.exists():
        fail("missing docs/ops-dashboard/data/runtime-executive-index.json")
    payload = json.loads(RUNTIME_EXECUTIVE_INDEX.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail("runtime-executive-index.json must be a JSON object")
    missing_keys = REQUIRED_INDEX_KEYS - set(payload)
    if missing_keys:
        fail(f"runtime-executive-index missing keys: {sorted(missing_keys)}")
    cards = payload.get("cards") or {}
    missing_cards = REQUIRED_INDEX_CARDS - set(cards)
    if missing_cards:
        fail(f"runtime-executive-index missing cards: {sorted(missing_cards)}")
    links = payload.get("links") or {}
    missing_links = REQUIRED_INDEX_LINKS - set(links)
    if missing_links:
        fail(f"runtime-executive-index missing links: {sorted(missing_links)}")


def main() -> int:
    try:
        validate_html()
        validate_index_contract()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "validated": "ops_dashboard_runtime_executive_panel"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
