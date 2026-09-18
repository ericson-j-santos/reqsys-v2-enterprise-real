from __future__ import annotations

import json
from pathlib import Path

from scripts.build_pr_workflow_run_metrics import build_metrics, load_runs, main


def test_build_metrics_groups_workflows_by_pr() -> None:
    payload = build_metrics(
        [
            {
                "name": "ReqSys Required Fast Gate",
                "status": "completed",
                "conclusion": "success",
                "pull_requests": [{"number": 766}],
                "html_url": "https://example.test/run/1",
            },
            {
                "name": "CI Enterprise Fast",
                "status": "completed",
                "conclusion": "success",
                "pull_requests": [{"number": 766}],
            },
            {
                "name": "PR Quality Review",
                "status": "completed",
                "conclusion": "failure",
                "pr_number": 765,
            },
            {
                "name": "Schedule Only",
                "status": "completed",
                "conclusion": "success",
            },
        ]
    )

    assert payload["summary"]["pr_count"] == 2
    assert payload["summary"]["ignored_without_pr"] == 1
    assert payload["summary"]["max_workflows_per_pr"] == 2
    assert payload["pull_requests"][0]["pr_number"] == 766
    assert payload["pull_requests"][0]["workflow_count"] == 2
    assert payload["pull_requests"][1]["failed_runs"] == 1


def test_load_runs_accepts_workflow_runs_shape(tmp_path: Path) -> None:
    input_path = tmp_path / "runs.json"
    input_path.write_text(
        json.dumps({"workflow_runs": [{"name": "Runtime Risk Scoring", "pr_number": 10}]}),
        encoding="utf-8",
    )

    assert load_runs(input_path) == [{"name": "Runtime Risk Scoring", "pr_number": 10}]


def test_main_writes_metrics_file(tmp_path: Path) -> None:
    input_path = tmp_path / "runs.json"
    output_path = tmp_path / "metrics.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "workflow_name": "ReqSys Required Fast Gate",
                    "status": "queued",
                    "pull_request_number": 123,
                }
            ]
        ),
        encoding="utf-8",
    )

    assert main(["--input", str(input_path), "--output", str(output_path)]) == 0

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["average_workflows_per_pr"] == 1
    assert payload["pull_requests"][0]["queued_or_running_runs"] == 1
