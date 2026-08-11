from datetime import UTC, datetime

from scripts.evaluate_current_sha_workflow_stability import evaluate_stability


POLICY = {
    "required_workflows": ["CI", "Evidence", "Security"],
    "allowed_conclusions": ["success", "neutral", "skipped"],
}


def run(
    name: str,
    *,
    sha: str = "abc",
    status: str = "completed",
    conclusion: str | None = "success",
    run_id: int = 1,
    created_at: str = "2026-07-31T18:00:00Z",
) -> dict:
    return {
        "id": run_id,
        "name": name,
        "head_sha": sha,
        "event": "pull_request",
        "status": status,
        "conclusion": conclusion,
        "created_at": created_at,
        "html_url": f"https://github.com/example/repo/actions/runs/{run_id}",
        "run_attempt": 1,
    }


def evaluate(runs: list[dict], *, current_sha: str = "abc") -> dict:
    return evaluate_stability(
        runs_payload={"workflow_runs": runs},
        policy=POLICY,
        evaluated_sha="abc",
        current_sha=current_sha,
        observed_at=datetime(2026, 7, 31, 18, 5, tzinfo=UTC),
    )


def test_stable_only_when_all_required_workflows_complete() -> None:
    report = evaluate([run("CI"), run("Evidence", run_id=2), run("Security", run_id=3)])
    assert report["stable"] is True
    assert report["decision"] == "stable"
    assert report["missing_workflows"] == []


def test_missing_workflow_is_not_success() -> None:
    report = evaluate([run("CI"), run("Evidence", run_id=2)])
    assert report["stable"] is False
    assert report["decision"] == "required_workflows_not_registered"
    assert report["missing_workflows"] == ["Security"]
    assert report["absence_is_success"] is False


def test_incomplete_workflow_blocks() -> None:
    report = evaluate(
        [run("CI"), run("Evidence", status="in_progress", conclusion=None, run_id=2), run("Security", run_id=3)]
    )
    assert report["decision"] == "required_workflows_incomplete"
    assert report["incomplete_workflows"] == [{"workflow": "Evidence", "status": "in_progress"}]


def test_failed_workflow_blocks() -> None:
    report = evaluate([run("CI"), run("Evidence", conclusion="failure", run_id=2), run("Security", run_id=3)])
    assert report["decision"] == "required_workflows_failed"


def test_head_sha_change_blocks_even_with_green_runs() -> None:
    report = evaluate(
        [run("CI"), run("Evidence", run_id=2), run("Security", run_id=3)],
        current_sha="new-sha",
    )
    assert report["stable"] is False
    assert report["decision"] == "head_sha_changed"


def test_latest_attempt_wins_over_cancelled_older_run() -> None:
    report = evaluate(
        [
            run("CI", conclusion="cancelled", run_id=1, created_at="2026-07-31T18:00:00Z"),
            run("CI", conclusion="success", run_id=4, created_at="2026-07-31T18:01:00Z"),
            run("Evidence", run_id=2),
            run("Security", run_id=3),
        ]
    )
    assert report["stable"] is True


def test_path_filtered_workflow_may_be_absent_but_still_blocks_when_failed() -> None:
    policy = {
        **POLICY,
        "optional_when_not_registered": ["Security"],
    }
    absent_report = evaluate_stability(
        runs_payload={"workflow_runs": [run("CI"), run("Evidence", run_id=2)]},
        policy=policy,
        evaluated_sha="abc",
        current_sha="abc",
        observed_at=datetime(2026, 7, 31, 18, 5, tzinfo=UTC),
    )
    assert absent_report["stable"] is True
    assert absent_report["missing_workflows"] == []
    assert absent_report["tolerated_missing_workflows"] == ["Security"]
    assert absent_report["absence_is_success"] is True

    failed_report = evaluate_stability(
        runs_payload={
            "workflow_runs": [
                run("CI"),
                run("Evidence", run_id=2),
                run("Security", conclusion="failure", run_id=3),
            ]
        },
        policy=policy,
        evaluated_sha="abc",
        current_sha="abc",
        observed_at=datetime(2026, 7, 31, 18, 5, tzinfo=UTC),
    )
    assert failed_report["stable"] is False
    assert failed_report["decision"] == "required_workflows_failed"
