from __future__ import annotations

import json
from pathlib import Path

from scripts.main_operational_state_snapshot import build_snapshot, main, render_markdown


def _validator(status: str = "passed", completeness: float = 100.0) -> dict:
    return {
        "contract": "post-merge-main-runtime-validator",
        "status": status,
        "sha": "abc",
        "github_run_id": "1",
        "evidence_completeness_percentual": completeness,
        "dominant_blocker": "none" if status == "passed" else "runtime_smoke",
        "links": {"runtime_public_url": "https://reqsys-app.fly.dev"},
    }


def test_build_snapshot_passes_from_valid_post_merge_report() -> None:
    snapshot = build_snapshot(_validator(), repo="example/repo", sha="abc", run_id="1")

    assert snapshot["contract"] == "main-operational-state-snapshot"
    assert snapshot["status"] == "passed"
    assert snapshot["branch"] == "main"
    assert snapshot["current_pr"] is None
    assert snapshot["wip"] == 0
    assert snapshot["dominant_blocker"] == "none"
    assert snapshot["critical_evidence"] == "present"
    assert snapshot["progress"]["operational"] == 100
    assert snapshot["progress"]["operational_risk"] == 4


def test_build_snapshot_blocks_when_post_merge_report_is_missing() -> None:
    snapshot = build_snapshot({}, repo="example/repo", sha="abc", run_id=None)

    assert snapshot["status"] == "blocked"
    assert snapshot["dominant_blocker"] == "post_merge_evidence_missing"
    assert snapshot["critical_evidence"] == "blocked_or_missing"
    assert snapshot["next_safe_increment"] == "none_until_snapshot_passes"


def test_build_snapshot_blocks_when_runtime_validator_blocks() -> None:
    snapshot = build_snapshot(_validator(status="blocked", completeness=50.0), repo="example/repo", sha="abc", run_id=None)

    assert snapshot["status"] == "blocked"
    assert snapshot["dominant_blocker"] == "runtime_smoke"
    assert snapshot["progress"]["operational"] == 50


def test_render_markdown_contains_operational_fields() -> None:
    snapshot = build_snapshot(_validator(), repo="example/repo", sha="abc", run_id="1")

    markdown = render_markdown(snapshot)

    assert "Estado Unico ReqSys" in markdown
    assert "Dominant blocker" in markdown
    assert "Human action required" in markdown
    assert "operational_risk" in markdown


def test_main_writes_snapshot_and_summary(tmp_path: Path, monkeypatch) -> None:
    validator_path = tmp_path / "validator.json"
    output_path = tmp_path / "out" / "snapshot.json"
    validator_path.write_text(json.dumps(_validator()), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "main_operational_state_snapshot.py",
            "--validator",
            str(validator_path),
            "--repo",
            "example/repo",
            "--sha",
            "abc",
            "--github-run-id",
            "1",
            "--output",
            str(output_path),
        ],
    )

    assert main() == 0
    assert output_path.exists()
    assert (output_path.parent / "summary.md").exists()
