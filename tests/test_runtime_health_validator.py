from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.runtime_health_validator import (  # noqa: E402
    WorkflowRun,
    build_baseline_report,
    build_health_matrix,
    build_quarantine,
    build_remediation_plan,
    build_report,
    build_retry_policy,
    compute_runtime_score,
    fetch_runs_with_fallback,
    write_report,
)


def run(
    name: str,
    conclusion: str | None = "success",
    status: str = "completed",
    run_id: int = 101,
    run_attempt: int = 1,
) -> WorkflowRun:
    return WorkflowRun(
        id=run_id,
        name=name,
        status=status,
        conclusion=conclusion,
        event="pull_request",
        branch="feature/runtime",
        sha="abc123",
        url=f"https://github.example/run/{run_id}",
        created_at="2026-06-26T00:00:00Z",
        updated_at="2026-06-26T00:01:00Z",
        run_attempt=run_attempt,
    )


def test_build_report_adds_governed_runtime_operational_layers() -> None:
    runs = [
        run("PR CI Watch", "cancelled"),
        run("Security Critical Gate", "failure"),
        run("CI — ReqSys v2 Enterprise", "success"),
    ]
    plan = build_remediation_plan(runs)

    report = build_report("owner/repo", "main", runs, plan, [], "dry_run")

    assert report["schema_version"] == "1.2.0"
    assert report["state"] == "red"
    assert report["executive_status"] == "Runtime com bloqueios operacionais"
    assert report["maturity"]["level"] == "reactive"
    assert report["runtime_score"] == report["maturity"]["score"]
    assert report["regression_detection"]["state"] == "regression_suspected"
    assert report["rollback_policy"]["automatic_destructive_actions"] is False
    assert report["environment_sync"]["strategy"] == "dev_to_homolog_to_prod"
    assert any(item["type"] == "gap" for item in report["automatic_backlog"])
    assert any(item["type"] == "remediation" for item in report["automatic_backlog"])


def test_health_matrix_and_quarantine_on_security_failure() -> None:
    runs = [
        run("Security Critical Gate", "failure"),
        run("CI — ReqSys v2 Enterprise", "success"),
    ]
    plan = build_remediation_plan(runs)
    report = build_report("owner/repo", "main", runs, plan, [], "report_only")

    matrix_ids = {row["id"] for row in report["health_matrix"]}
    assert matrix_ids == {"ci_github", "fly_dev", "fly_homolog", "fly_prod", "evidence_gate", "security_gates"}

    security_row = next(row for row in report["health_matrix"] if row["id"] == "security_gates")
    assert security_row["status"] == "red"
    assert report["quarantine"]["active"] is True
    assert "deploy" in report["quarantine"]["blocked_actions"]
    assert report["guardrails"]["deploy"] is True


def test_retry_policy_blocks_max_attempts() -> None:
    runs = [run("PR CI Watch", "cancelled", run_attempt=3)]
    plan = build_remediation_plan(runs)
    retry_policy = build_retry_policy(plan, runs, "execute")

    assert retry_policy["policy"] == "AOP-CI-RETRY-001"
    assert retry_policy["anti_loop_triggered"] is True
    assert retry_policy["allowed"] is False


def test_retry_policy_allows_eligible_execute_mode() -> None:
    runs = [run("PR CI Watch", "cancelled", run_attempt=1)]
    plan = build_remediation_plan(runs)
    retry_policy = build_retry_policy(plan, runs, "execute")

    assert retry_policy["eligible_reruns"] == 1
    assert retry_policy["allowed"] is True


def test_compute_runtime_score_weighted() -> None:
    matrix = build_health_matrix(
        [run("CI — ReqSys v2 Enterprise", "success")],
        probe_env=False,
        artifact_root=Path("."),
    )
    score = compute_runtime_score(matrix)
    assert 0 <= score <= 100
    assert score >= 70


def test_fetch_runs_with_fallback_uses_cached_artifact(tmp_path: Path) -> None:
    cached = {
        "runs": [
            {
                "id": 55,
                "name": "CI — ReqSys v2 Enterprise",
                "status": "completed",
                "conclusion": "success",
                "event": "push",
                "branch": "main",
                "sha": "deadbeef",
                "url": "https://github.example/run/55",
                "created_at": "2026-06-27T00:00:00Z",
                "updated_at": "2026-06-27T00:01:00Z",
                "run_attempt": 1,
            }
        ]
    }
    cached_path = tmp_path / "runtime-health-validator.json"
    cached_path.write_text(json.dumps(cached), encoding="utf-8")

    runs, data_sources, confidence = fetch_runs_with_fallback(
        "owner/repo",
        None,
        "main",
        50,
        cached_path,
    )

    assert len(runs) == 1
    assert runs[0].name == "CI — ReqSys v2 Enterprise"
    assert any(source["stage"] == "cached_artifact" for source in data_sources)
    assert confidence == "medium"


def test_build_baseline_report_when_no_data() -> None:
    report = build_baseline_report("owner/repo", "main", "report_only")

    assert report["confidence"] == "low"
    assert report["state"] == "green"
    assert report["runtime_score"] >= 0
    assert any(source["stage"] == "baseline" for source in report["data_sources"])


def test_write_report_publishes_navigable_summary_and_json(tmp_path: Path) -> None:
    report = build_report("owner/repo", "main", [run("CI", "success")], [], [], "report_only")

    write_report(report, tmp_path)

    payload = json.loads((tmp_path / "runtime-health-validator.json").read_text(encoding="utf-8"))
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")

    assert payload["maturity"]["level"] == "managed"
    assert "## Health matrix" in summary
    assert "## Quarantine" in summary
    assert "## Retry policy" in summary
    assert "## Automatic backlog" in summary
    assert "## Environment sync" in summary
    assert "https://reqsys-api.fly.dev/health" in summary
