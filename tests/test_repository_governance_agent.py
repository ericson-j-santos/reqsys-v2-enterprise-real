from pathlib import Path


WORKFLOW = Path(".github/workflows/repository-governance-agent.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_agent_runs_when_main_advances() -> None:
    text = _text()
    assert "push:" in text
    assert "branches: [main]" in text
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text


def test_agent_has_minimum_write_permission_for_update_branch() -> None:
    text = _text()
    assert "contents: write" in text
    assert "pull-requests: write" in text
    assert "issues: write" not in text
    assert "actions: write" not in text


def test_agent_limits_ci_fanout() -> None:
    text = _text()
    assert 'MAX_BRANCH_SYNCS: "3"' in text
    assert "updatesStarted >= maxSyncs" in text
    assert "branch_sync_budget_exhausted" in text


def test_agent_fails_closed_before_update_branch() -> None:
    text = _text()
    assert "current.head.sha !== expectedHeadSha" in text
    assert "current.mergeable === false" in text
    assert "current.mergeable_state === 'dirty'" in text
    assert "observed.mergeable === null" in text
    assert "external_fork" in text
    assert "draft" in text


def test_agent_uses_expected_head_sha() -> None:
    text = _text()
    assert "github.rest.pulls.updateBranch" in text
    assert "expected_head_sha: expectedHeadSha" in text
    assert "state_changed_before_update" in text


def test_agent_requires_independent_post_read() -> None:
    text = _text()
    assert "after.head.sha === expectedHeadSha" in text
    assert "afterComparison.behind_by" in text
    assert "update_not_confirmed" in text
    assert "core.setFailed" in text


def test_agent_never_merges_or_deploys() -> None:
    text = _text()
    assert "github.rest.pulls.merge" not in text
    assert "merge_method" not in text
    assert "github.rest.repos.createDeployment" not in text
    assert "fly deploy" not in text.lower()
    assert "force-push" not in text.lower()


def test_agent_has_single_concurrency_lane() -> None:
    text = _text()
    assert "group: repository-governance-agent-main-sync" in text
    assert "cancel-in-progress: true" in text


def test_global_sync_only_runs_for_main_push_or_manual_dispatch() -> None:
    text = _text()
    marker = "sync-open-prs:"
    block = text.split(marker, maxsplit=1)[1]
    assert "if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'" in block


def test_mutation_api_errors_fail_the_job() -> None:
    text = _text()
    assert "update_branch_api_" in text
    assert "mutationFailures" in text
    assert "core.setFailed" in text
