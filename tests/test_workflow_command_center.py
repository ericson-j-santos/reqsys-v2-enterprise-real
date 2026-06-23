from scripts.workflow_command_center import WorkflowRunSummary, build_report


def sample_run(name: str, status: str = "completed", conclusion: str | None = "success") -> WorkflowRunSummary:
    return WorkflowRunSummary(
        id=1,
        name=name,
        status=status,
        conclusion=conclusion,
        event="push",
        branch="main",
        commit_sha="abc123",
        url="",
        created_at="2026-06-23T10:00:00Z",
        updated_at="2026-06-23T10:05:00Z",
    )


def test_build_report_scores_healthy_critical_workflows() -> None:
    report = build_report([
        sample_run("CI — ReqSys v2 Enterprise"),
        sample_run("Governance Quality Gates"),
        sample_run("Governança Padrão Ouro"),
        sample_run("Main Post-Merge Validation"),
    ], None)

    assert report["status"] == "ok"
    assert report["operational_score"] >= 90
    assert report["metrics"]["success_rate_percent"] == 100.0


def test_build_report_marks_failed_critical_workflow_attention() -> None:
    report = build_report([
        sample_run("CI — ReqSys v2 Enterprise", conclusion="failure"),
        sample_run("Governance Quality Gates"),
    ], None)

    assert report["status"] == "attention"
    assert report["failed_critical_workflows"]
    assert report["operational_score"] < 90
