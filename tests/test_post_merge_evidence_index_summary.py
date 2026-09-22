from __future__ import annotations

import json
from pathlib import Path

from scripts.post_merge_evidence_index_summary import build_index, is_evidence_artifact, main, render_markdown


def _payload() -> dict:
    return {
        "runs": [
            {
                "id": 1,
                "name": "Main Post-Merge Validation",
                "event": "push",
                "status": "completed",
                "conclusion": "success",
                "head_branch": "main",
                "head_sha": "abc",
                "html_url": "https://github.com/example/repo/actions/runs/1",
                "artifacts": [
                    {"id": 10, "name": "main-post-merge-validation-abc", "size_in_bytes": 100, "expired": False},
                    {"id": 11, "name": "unrelated", "size_in_bytes": 10, "expired": False},
                ],
            },
            {
                "id": 2,
                "name": "CI",
                "event": "pull_request",
                "status": "completed",
                "conclusion": "success",
                "head_branch": "feature/x",
                "head_sha": "def",
                "artifacts": [],
            },
        ]
    }


def test_is_evidence_artifact_uses_operational_keywords() -> None:
    assert is_evidence_artifact("main-post-merge-validation-abc") is True
    assert is_evidence_artifact("runtime-report") is True
    assert is_evidence_artifact("plain-build-cache") is False


def test_build_index_focuses_on_main_evidence_artifacts() -> None:
    index = build_index(_payload(), repo="example/repo", branch="main", run_id="3")

    assert index["contract"] == "post-merge-evidence-index-summary"
    assert index["summary"]["status"] == "passed"
    assert index["summary"]["risk"] == "low"
    assert index["summary"]["main_runs"] == 1
    assert index["summary"]["evidence_runs"] == 1
    assert index["runs"][0]["evidence_artifact_count"] == 1


def test_build_index_warns_when_main_run_has_failure() -> None:
    payload = _payload()
    payload["runs"][0]["conclusion"] = "failure"

    index = build_index(payload, repo="example/repo", branch="main")

    assert index["summary"]["status"] == "warning"
    assert index["summary"]["completed_failures"] == 1
    assert index["summary"]["risk"] == "medium"


def test_build_index_attention_without_evidence() -> None:
    payload = {"runs": [{"id": 1, "name": "CI", "status": "completed", "conclusion": "success", "head_branch": "main", "artifacts": []}]}

    index = build_index(payload, repo="example/repo", branch="main")

    assert index["summary"]["status"] == "attention"
    assert index["summary"]["evidence_runs"] == 0


def test_render_markdown_contains_evidence_links() -> None:
    index = build_index(_payload(), repo="example/repo", branch="main")

    markdown = render_markdown(index)

    assert "Post-merge Evidence Index Summary" in markdown
    assert "Main Post-Merge Validation" in markdown
    assert "main-post-merge-validation-abc" in markdown


def test_main_writes_json_and_markdown(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "runs.json"
    output_dir = tmp_path / "out"
    input_path.write_text(json.dumps(_payload()), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "post_merge_evidence_index_summary.py",
            "--input",
            str(input_path),
            "--repo",
            "example/repo",
            "--branch",
            "main",
            "--github-run-id",
            "3",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert main() == 0
    assert (output_dir / "post-merge-evidence-index-summary.json").exists()
    assert (output_dir / "summary.md").exists()
