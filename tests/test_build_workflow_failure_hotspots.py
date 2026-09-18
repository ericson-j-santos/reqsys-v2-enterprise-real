from __future__ import annotations

import json
from pathlib import Path

from scripts.build_workflow_failure_hotspots import build_hotspots, load_runs, main


def test_workflow_failure_hotspots_classifies_recurring_failure_as_p1() -> None:
    payload = build_hotspots(
        [
            {
                "workflow_name": "CI Enterprise Fast",
                "status": "completed",
                "conclusion": "failure",
                "html_url": "https://example.test/1",
                "created_at": "2026-07-01T10:00:00Z",
            },
            {
                "workflow_name": "CI Enterprise Fast",
                "status": "completed",
                "conclusion": "failure",
                "html_url": "https://example.test/2",
                "created_at": "2026-07-01T11:00:00Z",
            },
            {
                "workflow_name": "CI Enterprise Fast",
                "status": "completed",
                "conclusion": "failure",
                "html_url": "https://example.test/3",
                "created_at": "2026-07-01T12:00:00Z",
            },
            {
                "workflow_name": "Runtime Smoke",
                "status": "completed",
                "conclusion": "success",
                "created_at": "2026-07-01T12:05:00Z",
            },
        ]
    )

    assert payload["summary"]["pareto_status"] == "red"
    assert payload["summary"]["p1_count"] == 1
    hotspot = payload["hotspots"][0]
    assert hotspot["workflow"] == "CI Enterprise Fast"
    assert hotspot["severity"] == "P1"
    assert hotspot["dominant_probable_cause"] == "falha_recorrente_no_mesmo_workflow"
    assert hotspot["minimum_evidence"]["latest_url"] == "https://example.test/3"


def test_workflow_failure_hotspots_reports_green_without_failures() -> None:
    payload = build_hotspots(
        [
            {"workflow_name": "PR Evidence Gate", "status": "completed", "conclusion": "success"},
            {"workflow_name": "Runtime Smoke", "status": "completed", "conclusion": "success"},
        ]
    )

    assert payload["summary"]["pareto_status"] == "green"
    assert payload["summary"]["hotspot_count"] == 0
    assert payload["hotspots"] == []


def test_load_runs_accepts_github_workflow_runs_shape(tmp_path: Path) -> None:
    input_path = tmp_path / "workflow-runs.json"
    input_path.write_text(
        json.dumps({"workflow_runs": [{"name": "Governed Merge Queue", "conclusion": "failure"}]}),
        encoding="utf-8",
    )

    runs = load_runs(input_path)

    assert runs == [{"name": "Governed Merge Queue", "conclusion": "failure"}]


def test_main_writes_output_file(tmp_path: Path) -> None:
    input_path = tmp_path / "runs.json"
    output_path = tmp_path / "hotspots.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "workflow_name": "Runtime Smoke",
                    "status": "in_progress",
                    "created_at": "2026-07-01T12:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert main(["--input", str(input_path), "--output", str(output_path)]) == 0

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["pareto_status"] == "yellow"
    assert payload["hotspots"][0]["workflow"] == "Runtime Smoke"
