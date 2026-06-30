#!/usr/bin/env python3
"""Validate the Ops Dashboard Pareto consolidation layer.

This validator is read-only and local-only. It verifies that the dashboard page
contains the expected DOM targets, data contract path and guardrail rendering
without making network calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs/ops-dashboard/operational-runtime-governance.html"
DATA_PATH = ROOT / "docs/ops-dashboard/data/operational-runtime-governance-consolidation.json"

REQUIRED_DOM_IDS = [
    "overall-status",
    "maturity-target",
    "operational-risk",
    "confidence",
    "bottleneck",
    "executive-links",
    "lane-cards",
    "lane-table",
    "actions-table",
    "sources-table",
    "guardrails-table",
    "raw-json",
]

REQUIRED_TEXT = [
    "Operational Runtime Governance — Pareto Layer",
    "operational-runtime-governance-consolidation.json",
    "renderExecutive",
    "renderLanes",
    "renderSources",
    "renderGuardrails",
    "fallback_local",
    "Ops Dashboard",
    "Operational Evidence Hub",
]

REQUIRED_LANES = {
    "ci_recovery_runtime_stability",
    "governance_hub_consolidated",
    "runtime_observability_p1",
    "contract_governance",
    "power_platform_runtime_layer",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def validate_html() -> None:
    if not HTML_PATH.exists():
        fail(f"missing dashboard layer: {HTML_PATH.relative_to(ROOT)}")
    text = HTML_PATH.read_text(encoding="utf-8")
    for dom_id in REQUIRED_DOM_IDS:
        if f'id="{dom_id}"' not in text:
            fail(f"missing DOM id: {dom_id}")
    for required in REQUIRED_TEXT:
        if required not in text:
            fail(f"missing required text/function: {required}")


def validate_data_contract() -> None:
    if not DATA_PATH.exists():
        fail(f"missing data contract: {DATA_PATH.relative_to(ROOT)}")
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    lanes = payload.get("pareto_lanes") or []
    lane_ids = {lane.get("id") for lane in lanes if isinstance(lane, dict)}
    missing = REQUIRED_LANES - lane_ids
    if missing:
        fail(f"missing required lanes in data contract: {sorted(missing)}")
    if not payload.get("canonical_sources"):
        fail("canonical_sources must not be empty")
    if not payload.get("guardrails"):
        fail("guardrails must not be empty")


def main() -> int:
    try:
        validate_html()
        validate_data_contract()
    except Exception as exc:  # noqa: BLE001 - CLI validator returns structured failure.
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "validated": "ops_dashboard_pareto_layer"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
