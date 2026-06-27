from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.trilha_d_qualidade_governanca import (  # noqa: E402
    consolidate,
    merge_state,
    run_ci_watch_dimension,
)


def dimension_fixture(
    dimension: str,
    *,
    status: str = "passed",
    score: float = 100.0,
    blockers: list[str] | None = None,
) -> dict:
    return {
        "dimension": dimension,
        "status": status,
        "score": score,
        "duration_seconds": 1.0,
        "summary": f"{dimension} ok",
        "details": {},
        "blockers": blockers or [],
        "recommendations": [],
    }


def test_merge_state_prefers_failed_over_warning_and_passed() -> None:
    assert merge_state("passed", "warning") == "warning"
    assert merge_state("warning", "failed") == "failed"
    assert merge_state("passed", "passed") == "passed"


def test_consolidate_marks_parallelizable_trail_d() -> None:
    report = consolidate(
        [
            dimension_fixture("tests"),
            dimension_fixture("coverage"),
            dimension_fixture("mutation"),
            dimension_fixture("contract"),
            dimension_fixture("schema"),
            dimension_fixture("ci-watch"),
        ],
        repository="owner/repo",
        run_id="123",
    )
    assert report["trail"] == "D"
    assert report["trail_name"] == "Qualidade e Governança"
    assert report["gold_standard"] is True
    assert report["parallelizable"] is True
    assert report["dimensions_total"] == 6
    assert report["state"] == "passed"
    assert report["decision"] == "continuar_incremento_qualidade"
    assert report["schema_version"] == "1.1.0"
    assert report["mode"] == "gold_standard"


def test_consolidate_failed_dimension_blocks_merge() -> None:
    report = consolidate(
        [
            dimension_fixture("tests", status="passed"),
            dimension_fixture("coverage", status="failed", score=40.0, blockers=["coverage abaixo"]),
        ],
        repository="owner/repo",
        run_id="456",
    )
    assert report["state"] == "failed"
    assert report["decision"] == "bloquear_merge_ate_corrigir_qualidade"
    assert any("coverage" in blocker for blocker in report["blockers"])


def test_ci_watch_dimension_passes_with_current_repo() -> None:
    result = run_ci_watch_dimension()
    assert result.dimension == "ci-watch"
    assert result.status == "passed"
    assert result.score == 100.0


def test_consolidated_report_matches_schema_required_fields() -> None:
    report = consolidate(
        [dimension_fixture("tests"), dimension_fixture("ci-watch")],
        repository="owner/repo",
        run_id="789",
    )
    schema_path = ROOT_DIR / "docs/contracts/trilha-d-qualidade-governanca.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for field in schema["required"]:
        assert field in report
