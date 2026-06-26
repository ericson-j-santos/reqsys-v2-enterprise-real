from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.runtime_health_validator import WorkflowRun, build_remediation_plan, build_report, write_report  # noqa: E402


def run(name: str, conclusion: str | None = "success", status: str = "completed") -> WorkflowRun:
    return WorkflowRun(
        id=101,
        name=name,
        status=status,
        conclusion=conclusion,
        event="pull_request",
        branch="feature/runtime",
        sha="abc123",
        url="https://github.example/run/101",
        created_at="2026-06-26T00:00:00Z",
        updated_at="2026-06-26T00:01:00Z",
    )


def test_build_report_adds_governed_runtime_operational_layers() -> None:
    runs = [
        run("PR CI Watch", "cancelled"),
        run("Security Critical Gate", "failure"),
        run("CI — ReqSys v2 Enterprise", "success"),
    ]
    plan = build_remediation_plan(runs)

    report = build_report("owner/repo", "main", runs, plan, [], "dry_run")

    assert report["schema_version"] == "1.1.0"
    assert report["state"] == "red"
    assert report["executive_status"] == "Runtime com bloqueios operacionais"
    assert report["maturity"]["level"] == "reactive"
    assert report["regression_detection"]["state"] == "regression_suspected"
    assert report["rollback_policy"]["automatic_destructive_actions"] is False
    assert report["environment_sync"]["strategy"] == "dev_to_homolog_to_prod"
    assert any(item["type"] == "gap" for item in report["automatic_backlog"])
    assert any(item["type"] == "remediation" for item in report["automatic_backlog"])


def test_write_report_publishes_navigable_summary_and_json(tmp_path: Path) -> None:
    report = build_report("owner/repo", "main", [run("CI", "success")], [], [], "report_only")

    write_report(report, tmp_path)

    payload = json.loads((tmp_path / "runtime-health-validator.json").read_text(encoding="utf-8"))
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")

    assert payload["maturity"]["level"] == "managed"
    assert "## Automatic backlog" in summary
    assert "## Environment sync" in summary
    assert "https://reqsys-api.fly.dev/health" in summary
