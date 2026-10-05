from pathlib import Path

WORKFLOW = Path(".github/workflows/governed-pr-automation.yml")


def test_state_machine_opens_only_opt_in_automation_branches() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "- Pre-PR Readiness Gate" in raw
    assert "open-pr-after-pre-pr:" in raw
    assert "github.event.workflow_run.conclusion == 'success'" in raw
    assert "startsWith(github.event.workflow_run.head_branch, 'automation/')" in raw


def test_state_machine_revalidates_exact_sha_before_pr_creation() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "ref.object.sha !== approvedSha" in raw
    assert "comparison.behind_by > 0" in raw
    assert "pulls.create" in raw
    assert "pr.head.sha !== approvedSha" in raw


def test_state_machine_is_idempotent_for_existing_pr() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "pulls.list" in raw
    assert "existing.length === 1" in raw
    assert "PR #" in raw


def test_state_transition_does_not_authorize_deploy_or_promotion() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    block = raw.split("  open-pr-after-pre-pr:", 1)[1].split("  increment-gate-on-open:", 1)[0]
    assert "deployments.create" not in block
    assert "repos.createDeployment" not in block
    assert "workflow_dispatch" not in block
    assert "A abertura não autoriza deploy ou promoção de ambiente." in block
