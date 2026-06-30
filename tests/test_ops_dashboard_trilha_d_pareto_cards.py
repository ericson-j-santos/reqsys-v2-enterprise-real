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

NAV_INDEX = ROOT / "docs/ops-dashboard/operational-navigation-index.json"
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


def test_ops_dashboard_exposes_trilha_d_history_card() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")
    for dom_id in TRILHA_D_DOM_IDS:
        assert f'id="{dom_id}"' in text, f"missing trilha d dom id: {dom_id}"


def test_ops_dashboard_exposes_operational_pareto_card() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")
    for dom_id in PARETO_DOM_IDS:
        assert f'id="{dom_id}"' in text, f"missing pareto dom id: {dom_id}"


def test_ops_dashboard_exposes_predictive_regression_card() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")
    for dom_id in PREDICTIVE_DOM_IDS:
        assert f'id="{dom_id}"' in text, f"missing predictive dom id: {dom_id}"


def test_ops_dashboard_exposes_continuous_monitoring_card() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")
    for dom_id in CONTINUOUS_MONITORING_DOM_IDS:
        assert f'id="{dom_id}"' in text, f"missing continuous monitoring dom id: {dom_id}"


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
    assert "predictive_regression_dashboard" in link_ids
    assert "continuous_trilha_d_monitoring_dashboard" in link_ids
    by_id = {item["id"]: item for item in payload["links"]}
    assert by_id["trilha_d_history_dashboard"]["href"] == "./index.html#trilha-d-history-card"
    assert by_id["operational_pareto_dashboard"]["href"] == "./index.html#operational-pareto-card"
    assert by_id["predictive_regression_dashboard"]["href"] == "./index.html#predictive-regression-card"
    assert by_id["continuous_trilha_d_monitoring_dashboard"]["href"] == "./index.html#continuous-trilha-d-monitoring-card"


def test_continuous_trilha_d_monitoring_artifact_contract() -> None:
    import json

    assert CONTINUOUS_MONITORING_DATA.exists(), "continuous-trilha-d-monitoring.json must be versioned for dashboard"
    payload = json.loads(CONTINUOUS_MONITORING_DATA.read_text(encoding="utf-8"))
    assert payload.get("schema_version")
    assert payload.get("state") is not None
    assert "links" in payload


def test_predictive_regression_gate_artifact_contract() -> None:
    import json

    assert PREDICTIVE_DATA.exists(), "predictive-regression-gate.json must be versioned for dashboard"
    payload = json.loads(PREDICTIVE_DATA.read_text(encoding="utf-8"))
    assert payload.get("schema_version")
    assert payload.get("risk") is not None
    assert "links" in payload


def test_validate_data_contracts_skips_cross_check_in_consolidation_mode(tmp_path, monkeypatch) -> None:
    import json

    from scripts import validate_ops_dashboard_trilha_d_pareto_cards as validator

    trilha_d = {
        "schema_version": "1.0.0",
        "current_score": 97.59,
        "summary": {"next_increment": "predictive_regression_gate"},
    }
    pareto = {
        "schema_version": "1.1.0",
        "current_score": 100.0,
        "summary": {"next_increment": None, "consolidation_mode": True},
    }
    predictive = {
        "schema_version": "1.0.0",
        "risk": "low",
    }
    monkeypatch.setattr(validator, "TRILHA_D_DATA", tmp_path / "trilha-d-history.json")
    monkeypatch.setattr(validator, "PARETO_DATA", tmp_path / "pareto.json")
    monkeypatch.setattr(validator, "PREDICTIVE_DATA", tmp_path / "predictive.json")
    (tmp_path / "trilha-d-history.json").write_text(json.dumps(trilha_d), encoding="utf-8")
    (tmp_path / "pareto.json").write_text(json.dumps(pareto), encoding="utf-8")
    (tmp_path / "predictive.json").write_text(json.dumps(predictive), encoding="utf-8")

    validator.validate_data_contracts()
