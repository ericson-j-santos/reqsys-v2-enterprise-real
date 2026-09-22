from __future__ import annotations

from scripts.build_strategic_governance_index import build_strategic_governance_index


def test_strategic_governance_index_prioritizes_runtime_when_readiness_is_high_risk() -> None:
    runtime_index = {
        "repo": "example/repo",
        "summary": {"executive_score": 72, "risk": "high", "confidence": "medium"},
        "cards": {
            "health": {"score": 90, "risk": "low"},
            "readiness": {"readiness_percent": 25, "risk": "high"},
            "merge_intelligence": {"mergeability_score": 88, "risk_level": "low"},
            "evidence_gate": {"risk": "low"},
            "finalization": {"final_score": 95, "risk": "low", "residual_gap": 0},
        },
    }

    payload = build_strategic_governance_index(runtime_index)

    assert payload["schema_version"] == "1.0.0"
    assert payload["repo"] == "example/repo"
    assert payload["summary"]["status"] == "action_required"
    assert payload["summary"]["top_priority_lane"] == "runtime_readiness"
    assert payload["summary"]["recommended_action"] == "stabilizar_evidencias_antes_de_expandir"
    assert payload["next_bottleneck"]["name"] == "runtime_publico_e_readiness"
    assert "priority_does_not_override_required_ci" in payload["guardrails"]


def test_strategic_governance_index_moves_to_prioritization_when_core_flow_is_low_risk() -> None:
    runtime_index = {
        "repo": "example/repo",
        "summary": {"executive_score": 92, "risk": "low", "confidence": "high"},
        "cards": {
            "health": {"score": 96, "risk": "low"},
            "readiness": {"readiness_percent": 95, "risk": "low"},
            "merge_intelligence": {"mergeability_score": 94, "risk_level": "low"},
            "evidence_gate": {"risk": "low"},
            "finalization": {"final_score": 98, "risk": "low", "residual_gap": 0},
        },
    }

    payload = build_strategic_governance_index(runtime_index)

    assert payload["summary"]["status"] == "governed"
    assert payload["summary"]["next_bottleneck"] == "priorizacao_estrategica_e_consolidacao"
    assert payload["next_bottleneck"]["recommended_increment"] == "strategic_governance_engine"
    assert payload["priority_lanes"][0]["priority_score"] >= payload["priority_lanes"][-1]["priority_score"]
    assert payload["decision_rules"]["execute_now_threshold"] == 80


def test_strategic_governance_index_fallback_is_safe_when_runtime_index_is_missing() -> None:
    payload = build_strategic_governance_index({}, repo="example/repo")

    assert payload["repo"] == "example/repo"
    assert payload["summary"]["runtime_executive_score"] == 0
    assert payload["summary"]["status"] == "action_required"
    assert payload["summary"]["recommended_action"] == "stabilizar_evidencias_antes_de_expandir"
    assert len(payload["priority_lanes"]) == 6
    assert "no_runtime_github_api_call" in payload["guardrails"]
