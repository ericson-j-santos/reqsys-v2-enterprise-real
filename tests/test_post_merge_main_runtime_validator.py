from __future__ import annotations

import json
from pathlib import Path

from scripts.post_merge_main_runtime_validator import build_report, main, render_markdown


def _smoke(status: str = "healthy") -> dict:
    return {
        "status": status,
        "base_url": "https://reqsys-app.fly.dev",
        "required_ok": 4,
        "required_total": 4,
        "required_success_percentual": 100.0,
    }


def _executive(status: str = "passed") -> dict:
    return {
        "contract": "executive-runtime-evidence-summary",
        "summary": {"status": status, "risk": "low", "production_ready": True},
        "cards": {"runtime_smoke": {}, "post_merge_sentinel": {}},
    }


def test_build_report_passes_when_smoke_and_executive_summary_are_valid() -> None:
    report = build_report(_smoke(), _executive(), repo="example/repo", sha="abc", run_id="1")

    assert report["contract"] == "post-merge-main-runtime-validator"
    assert report["schema_version"] == "1.1.0"
    assert report["status"] == "passed"
    assert report["risk"] == "low"
    assert report["evidence_completeness_percentual"] == 100.0
    assert report["dominant_blocker"] == "none"
    assert report["blocking_issues"] == []
    assert all(check["ok"] for check in report["checks"])


def test_build_report_blocks_when_smoke_is_missing() -> None:
    report = build_report({}, _executive(), repo="example/repo", sha="abc", run_id=None)

    assert report["status"] == "blocked"
    assert report["risk"] == "high"
    assert report["evidence_completeness_percentual"] == 50.0
    assert report["dominant_blocker"] == "runtime_smoke"
    assert "runtime_smoke" in report["blocking_issues"]


def test_build_report_blocks_when_executive_summary_contract_is_invalid() -> None:
    report = build_report(_smoke(), {"contract": "other"}, repo="example/repo", sha="abc", run_id=None)

    assert report["status"] == "blocked"
    assert report["dominant_blocker"] == "executive_runtime_evidence_summary"
    assert "executive_runtime_evidence_summary" in report["blocking_issues"]


def test_render_markdown_contains_checks_and_sha() -> None:
    report = build_report(_smoke(), _executive(), repo="example/repo", sha="abc", run_id="1")

    markdown = render_markdown(report)

    assert "Post-merge Main Runtime Validator" in markdown
    assert "runtime_smoke" in markdown
    assert "abc" in markdown
    assert "Evidence completeness" in markdown
    assert "Dominant blocker" in markdown


def test_main_writes_report_and_summary(tmp_path: Path, monkeypatch) -> None:
    smoke_path = tmp_path / "smoke.json"
    executive_path = tmp_path / "executive.json"
    output_path = tmp_path / "out" / "validator.json"
    smoke_path.write_text(json.dumps(_smoke()), encoding="utf-8")
    executive_path.write_text(json.dumps(_executive()), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "post_merge_main_runtime_validator.py",
            "--runtime-smoke",
            str(smoke_path),
            "--executive-summary",
            str(executive_path),
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
