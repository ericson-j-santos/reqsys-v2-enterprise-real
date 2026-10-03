from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.evaluate_promotion_release_gate import evaluate  # noqa: E402


def release_fixture(
    *,
    score: float = 96.0,
    readiness: str = "ready",
    operational_state: str = "green",
    blockers: list[str] | None = None,
) -> dict:
    return {
        "release_readiness_score": score,
        "readiness": readiness,
        "risk": "low",
        "operational_state": operational_state,
        "blockers": blockers or [],
        "warnings": [],
    }


def test_homolog_approves_ready_release() -> None:
    result = evaluate(release_fixture(), "homolog", dry_run=False, artifact_available=True)
    assert result["approved"] is True
    assert result["blocked_reason"] == ""


def test_homolog_blocks_low_score() -> None:
    result = evaluate(
        release_fixture(score=65.0, readiness="needs_review"),
        "homolog",
        dry_run=False,
        artifact_available=True,
    )
    assert result["approved"] is False
    assert "release_readiness_score_below_threshold" in result["blockers"]


def test_prod_requires_higher_readiness() -> None:
    result = evaluate(
        release_fixture(score=80.0, readiness="needs_review"),
        "prod",
        dry_run=False,
        artifact_available=True,
    )
    assert result["approved"] is False
    assert "release_readiness_needs_review" in result["blockers"]


def test_prod_blocks_yellow_operational_state() -> None:
    result = evaluate(
        release_fixture(score=96.0, readiness="ready_with_observation", operational_state="yellow"),
        "prod",
        dry_run=False,
        artifact_available=True,
    )
    assert result["approved"] is False
    assert "operational_state_yellow" in result["blockers"]


def test_missing_artifact_blocks_real_promotion() -> None:
    result = evaluate(None, "homolog", dry_run=False, artifact_available=False)
    assert result["approved"] is False
    assert "release_validation_artifact_missing" in result["blockers"]


def test_missing_artifact_allows_dry_run_with_warning() -> None:
    result = evaluate(None, "homolog", dry_run=True, artifact_available=False)
    assert result["approved"] is True
    assert result["promotion_would_block"] is True
    assert result["warnings"]


def test_blocked_readiness_blocks_promotion() -> None:
    result = evaluate(
        release_fixture(score=40.0, readiness="blocked", blockers=["operational_state_red"]),
        "homolog",
        dry_run=False,
        artifact_available=True,
    )
    assert result["approved"] is False
    assert "release_readiness_blocked" in result["blockers"]
