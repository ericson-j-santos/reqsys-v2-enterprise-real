from __future__ import annotations

import json
from pathlib import Path

from scripts.repository_health_watchdog import CheckResult, _normalize_title, write_outputs


def test_normalize_title_removes_draft_prefix_and_extra_spaces() -> None:
    assert _normalize_title("Draft:  Docs(CI):  Align workflow ") == "docs(ci): align workflow"


def test_write_outputs_marks_critical_failure(tmp_path: Path) -> None:
    result = CheckResult(
        name="main_smoke_ci",
        status="failed",
        severity="critical",
        evidence={"run_id": None},
        recommendation="Executar Main Smoke CI.",
    )

    exit_code = write_outputs([result], tmp_path, "owner/repo")

    assert exit_code == 1
    report = json.loads((tmp_path / "repository-health-report.json").read_text(encoding="utf-8"))
    assert report["overall_status"] == "failed"
    assert report["critical_failure_count"] == 1
    assert (tmp_path / "repository-health-summary.md").exists()


def test_write_outputs_passes_without_critical_or_warning(tmp_path: Path) -> None:
    result = CheckResult(
        name="duplicate_open_prs",
        status="passed",
        severity="info",
        evidence={"duplicate_groups": []},
        recommendation="Sem duplicidade.",
    )

    exit_code = write_outputs([result], tmp_path, "owner/repo")

    assert exit_code == 0
    report = json.loads((tmp_path / "repository-health-report.json").read_text(encoding="utf-8"))
    assert report["overall_status"] == "passed"
