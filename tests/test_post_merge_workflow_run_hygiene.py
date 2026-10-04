from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PR_EVIDENCE = ROOT / ".github" / "workflows" / "pr-evidence-gate.yml"
PR_CI_WATCH = ROOT / ".github" / "workflows" / "pr-ci-watch.yml"
OLLAMA = ROOT / ".github" / "workflows" / "ollama-ci-triage.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pr_only_workflow_run_paths_skip_default_branch_after_merge() -> None:
    evidence = read(PR_EVIDENCE)
    watch = read(PR_CI_WATCH)
    ollama = read(OLLAMA)

    assert "workflow_run_default_branch_post_merge" in evidence
    assert "github.event.workflow_run.head_branch" in evidence
    assert "github.event.repository.default_branch" in evidence

    assert (
        "if: github.event_name == 'workflow_run' && "
        "github.event.workflow_run.head_branch != github.event.repository.default_branch"
    ) in watch
    assert "workflow_run_default_branch_post_merge" in watch

    assert (
        "github.event.workflow_run.head_branch != "
        "github.event.repository.default_branch"
    ) in ollama
    assert "github.event.workflow_run.pull_requests[0].number" in ollama
