from scripts.auto_rerun_governed import WorkflowRun, build_report, classify_run


def sample_run(
    name: str = "CI — ReqSys v2 Enterprise",
    conclusion: str | None = "timed_out",
    run_attempt: int = 1,
) -> WorkflowRun:
    return WorkflowRun(
        id=123,
        name=name,
        status="completed",
        conclusion=conclusion,
        run_attempt=run_attempt,
        html_url="",
        head_branch="main",
        head_sha="abc123",
        event="push",
    )


def test_classify_transient_allowlisted_failure_for_rerun() -> None:
    decision = classify_run(sample_run())

    assert decision.decision == "rerun"
    assert decision.transient is True
    assert decision.allowlisted is True


def test_classify_non_allowlisted_workflow_blocks_rerun() -> None:
    decision = classify_run(sample_run(name="Random Workflow"))

    assert decision.decision == "blocked"
    assert decision.reason == "workflow_not_allowlisted"


def test_classify_governance_workflow_blocks_even_when_transient() -> None:
    decision = classify_run(sample_run(name="Governance Quality Gates"))

    assert decision.decision == "blocked"
    assert decision.reason == "workflow_blocklisted"


def test_classify_max_attempts_blocks_rerun() -> None:
    decision = classify_run(sample_run(run_attempt=2))

    assert decision.decision == "blocked"
    assert decision.reason == "max_rerun_attempts_reached"


def test_build_report_counts_eligible_and_blocked_decisions() -> None:
    decisions = [
        classify_run(sample_run()),
        classify_run(sample_run(name="Random Workflow")),
    ]

    report = build_report(decisions, dry_run=True)

    assert report["eligible_reruns"] == 1
    assert report["blocked"] == 1
    assert report["dry_run"] is True
