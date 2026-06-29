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

REQUIRED_FUNCTIONS = [
    "renderTrilhaDHistory",
    "renderOperationalPareto",
    "trilha-d-history.json",
    "padrao-ouro-operational-pareto.json",
]


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
