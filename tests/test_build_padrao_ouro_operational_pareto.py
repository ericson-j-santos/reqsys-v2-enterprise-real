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


def test_operational_pareto_prioritizes_visibility_after_coverage_target() -> None:
    payload = build_payload()

    assert payload["state"] == "yellow"
    assert payload["dominant_bottleneck"]["dimension"] == "coverage"
    assert payload["dominant_bottleneck"]["share_of_trilha_d_remaining_gap"] == 1.0
    assert payload["ranked_actions"][0]["id"] == "operational_pareto_dashboard_card"
    assert payload["ranked_actions"][0]["recommended_now"] is True


def test_operational_pareto_projects_gold_gap_closure() -> None:
    payload = build_payload()

    assert payload["current_score"] == 97.59
    assert payload["target_score"] == 98.0
    assert payload["gold_gap"] == 0.41
    assert payload["summary"]["evidence_source"] == "trilha_d_history"
    assert payload["dimension_gaps"]["coverage"] == 14.44
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
    trilha_d = load_trilha_d_evidence(__import__("pathlib").Path("docs/ops-dashboard/data/trilha-d-history.json"))
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
