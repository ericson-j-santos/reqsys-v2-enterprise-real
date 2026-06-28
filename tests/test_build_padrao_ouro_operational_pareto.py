from __future__ import annotations

from scripts.build_padrao_ouro_operational_pareto import build_payload, score_action, trend_for if False else build_ranked_actions


def test_operational_pareto_prioritizes_coverage_first() -> None:
    payload = build_payload()

    assert payload["state"] == "green"
    assert payload["dominant_bottleneck"]["dimension"] == "coverage"
    assert payload["dominant_bottleneck"]["share_of_trilha_d_remaining_gap"] == 1.0
    assert payload["ranked_actions"][0]["id"] == "coverage_targeted_tests"
    assert payload["ranked_actions"][0]["recommended_now"] is True


def test_operational_pareto_projects_gold_gap_closure() -> None:
    payload = build_payload()

    assert payload["current_score"] == 95.88
    assert payload["target_score"] == 98.0
    assert payload["gold_gap"] == 2.12
    assert payload["projected_score_after_recommended"] == 100.0
    assert payload["projected_gap_after_recommended"] == 0.0


def test_score_action_rewards_high_gain_low_effort_low_risk() -> None:
    high_value = {
        "expected_score_gain": 4.0,
        "confidence": 0.8,
        "effort_points": 2,
        "risk": "low",
    }
    low_value = {
        "expected_score_gain": 1.0,
        "confidence": 0.5,
        "effort_points": 5,
        "risk": "medium",
    }

    assert score_action(high_value) > score_action(low_value)


def test_build_ranked_actions_marks_two_recommended_now() -> None:
    ranked = build_ranked_actions()
    recommended = [item for item in ranked if item["recommended_now"]]

    assert len(recommended) == 2
    assert recommended[0]["pareto_score"] >= recommended[1]["pareto_score"]
