from __future__ import annotations

from scripts.runtime_merge_queue_gate import evaluate_gate


def test_runtime_merge_queue_gate_allows_green_runtime() -> None:
    result = evaluate_gate(
        lane="runtime-governance",
        ci="green",
        runtime_smoke="green",
        incidents="none-critical",
        contracts="green",
        mergeable="true",
    )

    assert result["eligible"] is True
    assert result["state"] == "eligible"
    assert result["blocking_reasons"] == []


def test_runtime_merge_queue_gate_blocks_critical_incident() -> None:
    result = evaluate_gate(
        lane="runtime-governance",
        ci="green",
        runtime_smoke="green",
        incidents="critical",
        contracts="green",
        mergeable="true",
    )

    assert result["eligible"] is False
    assert result["state"] == "paused_by_incident"
    assert "critical_incident_open" in result["blocking_reasons"]


def test_runtime_merge_queue_gate_requires_rebase_when_not_mergeable() -> None:
    result = evaluate_gate(
        lane="runtime-governance",
        ci="green",
        runtime_smoke="green",
        incidents="none-critical",
        contracts="green",
        mergeable="false",
    )

    assert result["eligible"] is False
    assert result["state"] == "requires_rebase"
    assert "not_mergeable" in result["blocking_reasons"]
