from __future__ import annotations

from scripts.build_padrao_ouro_operational_pareto import (
    ACTION_CATALOG,
    build_payload,
    build_ranked_actions,
    compute_dimension_gaps,
    derive_bottleneck,
    enrich_actions,
    load_trilha_d_evidence,
    score_action,
)


def test_operational_pareto_avanca_para_dashboard_apos_governanca_deep_links() -> None:
    from scripts.build_trilha_d_history import (
        NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION,
        NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD,
        governance_workflow_deep_links_surface_ready,
        resolve_next_increment,
    )

    if governance_workflow_deep_links_surface_ready():
        assert resolve_next_increment(artifact_ingestion=True) in {
            NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD,
            NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION,
        }
    payload = build_payload(from_evidence=True)
    trilha_d = load_trilha_d_evidence(__import__("pathlib").Path("docs/ops-dashboard/data/trilha-d-history.json"))
    assert trilha_d.get("next_increment") in {
        "dashboard_trilha_d_history_card",
        "artifact_ingestion_refresh",
        "merge_readiness_history",
        "link_governance_cards_to_latest_workflow_runs",
        "continuous_trilha_d_monitoring",
    }
    assert payload["summary"]["evidence_source"] == "trilha_d_history"


def test_operational_pareto_projects_gold_gap_closure() -> None:
    payload = build_payload(from_evidence=True)

    assert payload["current_score"] >= 97.0
    assert payload["target_score"] == 98.0
    assert payload["gold_gap"] <= 1.0
    assert payload["summary"]["evidence_source"] == "trilha_d_history"
    assert payload["dimension_gaps"]["coverage"] <= 18.0
    assert payload["projected_score_after_recommended"] >= payload["current_score"]


def test_score_action_rewards_high_gap_low_effort_low_risk() -> None:
    gaps = {"coverage": 25.0, "tests": 0.0}
    high_value = {
        "dimension": "coverage",
        "expected_score_gain": 1.2,
        "confidence": 0.8,
        "effort_points": 2,
        "risk": "low",
    }
    low_value = {
        "dimension": "operational-visibility",
        "expected_score_gain": 1.0,
        "confidence": 0.5,
        "effort_points": 5,
        "risk": "medium",
    }

    assert score_action(high_value, gaps=gaps) > score_action(low_value, gaps=gaps)


def test_build_ranked_actions_applies_pareto_80_20() -> None:
    trilha_d = {
        "artifact_ingestion_enabled": True,
        "next_increment": "artifact_ingestion_refresh",
        "dimension_signals": {"coverage": 74.0, "tests": 100.0, "mutation": 100.0, "contract": 100.0, "schema": 100.0, "ci-watch": 100.0},
    }
    signals = trilha_d["dimension_signals"]
    gaps = compute_dimension_gaps(signals)
    ranked = build_ranked_actions(signals, gaps, trilha_d)
    recommended = [item for item in ranked if item["recommended_now"]]

    assert recommended
    assert recommended[0]["pareto_score"] >= recommended[-1]["pareto_score"]
    assert recommended[-1]["cumulative_expected_gain_pct"] <= 80.0 or len(recommended) == 1


def test_consolidation_mode_reaches_100() -> None:
    payload = build_payload(consolidation=True)

    assert payload["current_score"] == 100.0
    assert payload["dominant_bottleneck"]["dimension"] == "none"
    assert payload["summary"]["recommended_now"] == 0


def test_derive_bottleneck_is_statistically_weighted() -> None:
    signals = {"coverage": 74.29, "tests": 100.0}
    gaps = compute_dimension_gaps(signals)
    bottleneck = derive_bottleneck(signals, gaps)

    assert bottleneck["dimension"] == "coverage"
    assert bottleneck["gap_to_100"] == 25.71
    assert bottleneck["share_of_trilha_d_remaining_gap"] == 1.0


def test_enrich_actions_skips_dimensions_already_at_target() -> None:
    trilha_d = {"artifact_ingestion_enabled": True, "next_increment": "done"}
    signals = {dimension: 100.0 for dimension in ("tests", "coverage", "mutation", "contract", "schema", "ci-watch")}
    gaps = compute_dimension_gaps(signals)
    actions = enrich_actions(ACTION_CATALOG, signals=signals, gaps=gaps, trilha_d=trilha_d)

    assert all(action["dimension"] != "coverage" for action in actions)
