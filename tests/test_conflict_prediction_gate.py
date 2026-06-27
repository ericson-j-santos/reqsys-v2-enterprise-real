from __future__ import annotations

from scripts.conflict_prediction_gate import classify_conflict


def test_conflict_prediction_allows_docs_only_parallel() -> None:
    result = classify_conflict(["artifacts/runtime-governance/example.md"])

    assert result["risk"] == "low"
    assert result["parallel_safe"] is True
    assert result["signals"]["artifact_only"] is True


def test_conflict_prediction_marks_runtime_surface_as_high() -> None:
    result = classify_conflict(["backend/app/api/runtime_validator.py"])

    assert result["risk"] == "high"
    assert result["parallel_safe"] is False
    assert result["signals"]["runtime_surface_change"] is True


def test_conflict_prediction_blocks_overlap() -> None:
    result = classify_conflict(["frontend/src/router/index.js"], overlap=True)

    assert result["risk"] == "blocked"
    assert result["parallel_safe"] is False
    assert "changed_paths_overlap" in result["blocking_reasons"]
