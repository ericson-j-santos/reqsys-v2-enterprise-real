from pathlib import Path
import json
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ci_intelligence_lib import (  # noqa: E402
    build_maturity_snapshot,
    calculate_maturity_trend,
    derive_maturity_signals,
    merge_maturity_history,
)
from scripts.delivery_maturity_snapshot import apply_signals, build_report, semaphore  # noqa: E402


SAMPLE_CI_REPORT = {
    "operational_score": 72,
    "runs_analyzed": 12,
    "matches_total": 2,
    "status": "AMARELO",
    "categories": {"test_failure": 1},
    "instability": {"rate_percent": 25.0},
    "pareto_failures": {
        "total_causes": 1,
        "top_causes": [{"name": "pytest failed", "category": "test_failure"}],
    },
    "rerun_assessment": {"blocked": False},
    "recommended_next_actions": ["Corrigir regressao de teste."],
    "instability_history": {"trend": {"direction": "estavel"}},
}

SAMPLE_PR_EVIDENCE_PASSED = {
    "gate": {"status": "passed"},
    "pr": {"head_sha": "abc123"},
}

SAMPLE_PR_EVIDENCE_FAILED = {
    "gate": {"status": "failed", "failures": ["CI failed"]},
    "pr": {"head_sha": "def456"},
}


def test_semaphore_levels() -> None:
    assert semaphore(90, 2, "high") == "verde"
    assert semaphore(85, 8, "medium") == "amarelo"
    assert semaphore(70, 25, "low") == "vermelho"


def test_derive_maturity_signals_from_ci_report() -> None:
    signals = derive_maturity_signals(ci_report=SAMPLE_CI_REPORT)

    assert signals["técnico"]["current_percent"] == 72.0
    assert signals["operacional"]["current_percent"] == 75.0
    assert signals["técnico"]["confidence_level"] == "high"


def test_derive_maturity_signals_boosts_on_pr_evidence_passed() -> None:
    signals = derive_maturity_signals(ci_report=SAMPLE_CI_REPORT, pr_evidence=SAMPLE_PR_EVIDENCE_PASSED)

    assert signals["evidência"]["current_percent"] >= 92.0
    assert signals["evidência"]["confidence_level"] == "high"


def test_derive_maturity_signals_penalizes_on_pr_evidence_failed() -> None:
    signals = derive_maturity_signals(ci_report=SAMPLE_CI_REPORT, pr_evidence=SAMPLE_PR_EVIDENCE_FAILED)

    assert signals["evidência"]["current_percent"] <= 55.0
    assert signals["técnico"]["current_percent"] <= 60.0


def test_build_report_with_ci_sources_includes_continuous_score() -> None:
    report = build_report(ci_report=SAMPLE_CI_REPORT, head_sha="abc123", history=[])

    assert report["schema_version"] == "1.1.0"
    assert report["head_sha"] == "abc123"
    assert "operational_ci_intelligence" in report["sources"]
    assert report["continuous_score"] > 0
    assert report["maturity_history"]["points"] == 1
    assert "técnico" in {item["name"] for item in report["dimensions"]}


def test_build_report_without_sources_uses_static_fallbacks() -> None:
    report = build_report(history=[])

    assert report["schema_version"] == "1.1.0"
    assert report["sources"] == {}
    assert len(report["dimensions"]) == 8
    assert report["dimensions"][0]["current_percent"] == 86.0


def test_merge_maturity_history_respects_max_items() -> None:
    existing = [{"snapshot_at_utc": f"2026-06-0{i}T00:00:00+00:00"} for i in range(1, 5)]
    snapshot = {"snapshot_at_utc": "2026-06-10T00:00:00+00:00", "continuous_score": 80}
    merged = merge_maturity_history(existing, snapshot, max_items=3)

    assert len(merged) == 3
    assert merged[-1]["continuous_score"] == 80


def test_calculate_maturity_trend_improving() -> None:
    history = [
        {"continuous_score": 70, "average_gap_percent": 15},
        {"continuous_score": 85, "average_gap_percent": 10},
    ]
    trend = calculate_maturity_trend(history)

    assert trend["direction"] == "melhorando"
    assert trend["delta_score"] == 15.0


def test_apply_signals_overrides_dimension() -> None:
    from scripts.delivery_maturity_snapshot import DIMENSIONS

    updated = apply_signals(DIMENSIONS, {"técnico": {"current_percent": 95.0, "confidence_level": "high"}})
    tecnico = next(item for item in updated if item["name"] == "técnico")

    assert tecnico["current_percent"] == 95.0
    assert tecnico["confidence_level"] == "high"
    assert tecnico["gap_percent"] == 3.0
