#!/usr/bin/env python3
"""Validate Trilha D history, Operational Pareto and Predictive Regression cards in the Ops Dashboard.

Read-only validator for static HTML/JSON artifacts. Does not perform network calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "docs/ops-dashboard/index.html"
NAV_INDEX = ROOT / "docs/ops-dashboard/operational-navigation-index.json"
TRILHA_D_DATA = ROOT / "docs/ops-dashboard/data/trilha-d-history.json"
PARETO_DATA = ROOT / "docs/ops-dashboard/data/padrao-ouro-operational-pareto.json"
PREDICTIVE_DATA = ROOT / "docs/ops-dashboard/data/predictive-regression-gate.json"
CONTINUOUS_MONITORING_DATA = ROOT / "docs/ops-dashboard/data/continuous-trilha-d-monitoring.json"

CONTINUOUS_MONITORING_DOM_IDS = [
    "continuous-monitoring-state",
    "continuous-monitoring-enabled",
    "continuous-monitoring-regression-alert",
    "continuous-monitoring-alerts-count",
    "continuous-monitoring-signals",
    "continuous-monitoring-alerts-rows",
    "continuous-monitoring-links",
    "continuous-monitoring-details",
]

TRILHA_D_DOM_IDS = [
    "trilha-d-score",
    "trilha-d-state",
    "trilha-d-trend",
    "trilha-d-delta",
    "trilha-d-dimensions",
    "trilha-d-history-rows",
    "trilha-d-links",
    "trilha-d-details",
]

PARETO_DOM_IDS = [
    "pareto-score",
    "pareto-gold-gap",
    "pareto-bottleneck",
    "pareto-confidence",
    "pareto-rule",
    "pareto-actions",
    "pareto-links",
    "pareto-details",
]

PREDICTIVE_DOM_IDS = [
    "predictive-risk",
    "predictive-regression-predicted",
    "predictive-parallel-safe",
    "predictive-recommendation",
    "predictive-signals",
    "predictive-dimension-risks",
    "predictive-blocking-reasons",
    "predictive-links",
    "predictive-details",
]

REQUIRED_SECTION_IDS = [
    "operational-intelligence-nav",
    "trilha-d-history-card",
    "operational-pareto-card",
    "predictive-regression-card",
    "continuous-trilha-d-monitoring-card",
]

REQUIRED_FUNCTIONS = [
    "renderTrilhaDHistory",
    "renderOperationalPareto",
    "renderPredictiveRegressionGate",
    "renderContinuousTrilhaDMonitoring",
    "renderOperationalIntelligenceQuickLinks",
    "trilha-d-history.json",
    "padrao-ouro-operational-pareto.json",
    "predictive-regression-gate.json",
    "continuous-trilha-d-monitoring.json",
]

REQUIRED_NAV_LINK_IDS = {
    "trilha_d_history_dashboard",
    "operational_pareto_dashboard",
    "predictive_regression_dashboard",
    "continuous_trilha_d_monitoring_dashboard",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def validate_index_html() -> None:
    if not INDEX_HTML.exists():
        fail(f"missing dashboard page: {INDEX_HTML.relative_to(ROOT)}")
    text = INDEX_HTML.read_text(encoding="utf-8")
    for dom_id in [*TRILHA_D_DOM_IDS, *PARETO_DOM_IDS, *PREDICTIVE_DOM_IDS, *CONTINUOUS_MONITORING_DOM_IDS, *REQUIRED_SECTION_IDS]:
        if f'id="{dom_id}"' not in text:
            fail(f"missing DOM id: {dom_id}")
    for required in REQUIRED_FUNCTIONS:
        if required not in text:
            fail(f"missing required renderer/data reference: {required}")


def validate_navigation_links() -> None:
    if not NAV_INDEX.exists():
        fail(f"missing navigation index: {NAV_INDEX.relative_to(ROOT)}")
    payload = json.loads(NAV_INDEX.read_text(encoding="utf-8"))
    link_ids = {item.get("id") for item in payload.get("links") or [] if isinstance(item, dict)}
    missing = REQUIRED_NAV_LINK_IDS - link_ids
    if missing:
        fail(f"missing required navigation links: {sorted(missing)}")
    by_id = {item["id"]: item for item in payload["links"]}
    assert by_id["trilha_d_history_dashboard"]["href"] == "./index.html#trilha-d-history-card"
    assert by_id["operational_pareto_dashboard"]["href"] == "./index.html#operational-pareto-card"
    assert by_id["predictive_regression_dashboard"]["href"] == "./index.html#predictive-regression-card"
    assert by_id["continuous_trilha_d_monitoring_dashboard"]["href"] == "./index.html#continuous-trilha-d-monitoring-card"


def validate_data_contracts() -> None:
    for path in (TRILHA_D_DATA, PARETO_DATA, PREDICTIVE_DATA, CONTINUOUS_MONITORING_DATA):
        if not path.exists():
            fail(f"missing data contract: {path.relative_to(ROOT)}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not payload.get("schema_version"):
            fail(f"schema_version missing in {path.relative_to(ROOT)}")
        if path == PREDICTIVE_DATA:
            if payload.get("risk") is None:
                fail("risk missing in predictive-regression-gate.json")
            continue
        if path == CONTINUOUS_MONITORING_DATA:
            if payload.get("state") is None:
                fail("state missing in continuous-trilha-d-monitoring.json")
            continue
        if not isinstance(payload.get("current_score"), int | float):
            fail(f"current_score missing in {path.relative_to(ROOT)}")

    trilha_d = json.loads(TRILHA_D_DATA.read_text(encoding="utf-8"))
    pareto = json.loads(PARETO_DATA.read_text(encoding="utf-8"))
    pareto_summary = pareto.get("summary") or {}
    if pareto_summary.get("consolidation_mode"):
        return

    trilha_next = (trilha_d.get("summary") or {}).get("next_increment")
    pareto_next = pareto_summary.get("next_increment")
    aligned_pairs = {
        "predictive_regression_gate",
        "coverage_targeted_tests",
        "link_governance_cards_to_latest_workflow_runs",
        "continuous_trilha_d_monitoring",
        "link_governance_cards_to_latest_workflow_runs",
    }
    if trilha_next in aligned_pairs and pareto_next != trilha_next:
        fail(
            "pareto next_increment diverges from trilha-d-history after dashboard consolidation: "
            f"trilha_d={trilha_next!r} pareto={pareto_next!r}"
        )
    if isinstance(trilha_d.get("current_score"), int | float) and isinstance(pareto.get("current_score"), int | float):
        if trilha_d["current_score"] != pareto["current_score"]:
            fail(
                "current_score diverges between trilha-d-history and pareto index: "
                f"trilha_d={trilha_d['current_score']} pareto={pareto['current_score']}"
            )


def main() -> int:
    try:
        validate_index_html()
        validate_navigation_links()
        validate_data_contracts()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(
        json.dumps({"status": "passed", "validated": "ops_dashboard_trilha_d_pareto_cards"}, ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
