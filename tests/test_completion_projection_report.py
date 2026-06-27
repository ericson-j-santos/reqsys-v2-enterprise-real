import json
from pathlib import Path

from scripts.completion_projection_report import (
    build_report,
    render_markdown,
    write_artifacts,
)

CONTRACT_PATH = Path("docs/contracts/completion-projection-report.schema.json")


def test_build_report_computes_derived_metrics() -> None:
    report = build_report(repository="org/reqsys", run_id="123", event_name="push")

    # Averages derived from the source tables (kept internally consistent).
    assert report["overall_completion_percent"] == 63.0
    assert report["average_maturity_percent"] == 71.2
    assert report["average_gap_pp"] == 24.9
    assert report["remaining_to_gold_pp"] == 48.0
    assert report["status"] == "em_aceleracao"
    assert report["mode"] == "report_only"
    assert report["repository"] == "org/reqsys"
    assert report["run_id"] == "123"
    assert report["event_name"] == "push"


def test_build_report_satisfies_contract_required_keys() -> None:
    report = build_report()
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    for key in schema["required"]:
        assert key in report, f"missing contract key: {key}"

    # Percentage fields stay within bounds.
    for key in (
        "overall_completion_percent",
        "average_maturity_percent",
        "average_gap_pp",
        "remaining_to_gold_pp",
    ):
        assert 0 <= report[key] <= 100

    for item in report["probabilities"]:
        assert 0 <= item["probability_percent"] <= 100
    for item in report["completion"]:
        assert 0 <= item["percent"] <= 100


def test_status_enum_matches_contract() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    allowed = set(schema["properties"]["status"]["enum"])
    assert build_report()["status"] in allowed


def test_write_artifacts_persists_json_and_markdown(tmp_path: Path) -> None:
    report = build_report(repository="org/reqsys")
    write_artifacts(report, tmp_path)

    json_path = tmp_path / "completion-projection-report.json"
    md_path = tmp_path / "completion-projection-report.md"
    assert json_path.exists()
    assert md_path.exists()

    persisted = json.loads(json_path.read_text(encoding="utf-8"))
    assert persisted["overall_completion_percent"] == report["overall_completion_percent"]

    markdown = md_path.read_text(encoding="utf-8")
    assert "Completion Projection Report" in markdown
    assert "report_only" in markdown


def test_render_markdown_lists_all_indicators() -> None:
    report = build_report()
    markdown = render_markdown(report)
    for item in report["completion"]:
        assert item["indicator"] in markdown
