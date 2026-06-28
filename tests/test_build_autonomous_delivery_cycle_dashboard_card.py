from __future__ import annotations

from scripts.build_autonomous_delivery_cycle_dashboard_card import build_card


def test_build_card_uses_safe_seed_fallback() -> None:
    payload = build_card({}, {})

    assert payload["schema_version"] == "1.0.0"
    assert payload["card"] == "autonomous_delivery_cycle"
    assert payload["status"] == "seed"
    assert payload["metrics"]["candidate_count"] == 0
    assert payload["metrics"]["next_increment_queue_count"] == 0
    assert "safe_fallback_when_source_artifact_missing" in payload["guardrails"]


def test_build_card_exposes_queue_and_counts() -> None:
    latest = {
        "mode": "merge_enabled",
        "required_label": "cycle:auto-merge-approved",
        "candidate_count": 2,
        "eligible_count": 1,
        "merged_count": 1,
        "decisions": [
            {"blockers": []},
            {"blockers": ["Workflow obrigatório ausente: CI"]},
        ],
    }
    queue = {
        "status": "queued",
        "queue": [
            {"source_pr": 460, "title": "Consumir contratos no dashboard", "status": "queued_for_chat_execution"}
        ],
    }

    payload = build_card(latest, queue)

    assert payload["status"] == "passed"
    assert payload["risk"] == "high"
    assert payload["metrics"]["candidate_count"] == 2
    assert payload["metrics"]["eligible_count"] == 1
    assert payload["metrics"]["merged_count"] == 1
    assert payload["metrics"]["blocker_count"] == 1
    assert payload["metrics"]["next_increment_queue_count"] == 1
    assert payload["queue"]["items"][0]["source_pr"] == 460


def test_build_card_marks_post_merge_attention_as_high_risk() -> None:
    latest = {
        "decisions": [
            {"post_merge": {"status": "post_merge_attention_required"}},
        ]
    }

    payload = build_card(latest, {})

    assert payload["status"] == "post_merge_attention_required"
    assert payload["risk"] == "high"
    assert "post_merge_attention_blocks_next_increment" in payload["guardrails"]
