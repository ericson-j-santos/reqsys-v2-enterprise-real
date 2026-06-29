from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "docs/ops-dashboard/index.html"

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

REQUIRED_SECTION_IDS = [
    "operational-intelligence-nav",
    "trilha-d-history-card",
    "operational-pareto-card",
]

REQUIRED_FUNCTIONS = [
    "renderTrilhaDHistory",
    "renderOperationalPareto",
    "renderOperationalIntelligenceQuickLinks",
    "trilha-d-history.json",
    "padrao-ouro-operational-pareto.json",
]

NAV_INDEX = ROOT / "docs/ops-dashboard/operational-navigation-index.json"


def test_ops_dashboard_exposes_trilha_d_history_card() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")
    for dom_id in TRILHA_D_DOM_IDS:
        assert f'id="{dom_id}"' in text, f"missing trilha d dom id: {dom_id}"


def test_ops_dashboard_exposes_operational_pareto_card() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")
    for dom_id in PARETO_DOM_IDS:
        assert f'id="{dom_id}"' in text, f"missing pareto dom id: {dom_id}"


def test_ops_dashboard_wires_trilha_d_and_pareto_renderers() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")
    for required in REQUIRED_FUNCTIONS:
        assert required in text, f"missing required renderer/data reference: {required}"


def test_ops_dashboard_exposes_anchor_sections_for_deep_links() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")
    for section_id in REQUIRED_SECTION_IDS:
        assert f'id="{section_id}"' in text, f"missing section anchor: {section_id}"


def test_operational_navigation_index_links_trilha_d_and_pareto() -> None:
    import json

    payload = json.loads(NAV_INDEX.read_text(encoding="utf-8"))
    link_ids = {item.get("id") for item in payload.get("links") or []}
    assert "trilha_d_history_dashboard" in link_ids
    assert "operational_pareto_dashboard" in link_ids
    by_id = {item["id"]: item for item in payload["links"]}
    assert by_id["trilha_d_history_dashboard"]["href"] == "./index.html#trilha-d-history-card"
    assert by_id["operational_pareto_dashboard"]["href"] == "./index.html#operational-pareto-card"
