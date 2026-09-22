from pathlib import Path


WORKFLOW = Path(".github/workflows/repository-governance-agent.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_agent_runs_when_main_advances_and_uses_trusted_pr_target() -> None:
    text = _text()
    assert "push:" in text
    assert "pull_request_target:" in text
    assert "\n  pull_request:\n" not in text
    assert "branches: [main]" in text
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text


def test_builtin_token_is_read_only_and_app_token_is_contents_write_only() -> None:
    text = _text()
    header = text.split("jobs:", maxsplit=1)[0]

    assert "permissions:\n  contents: read\n  pull-requests: read" in header
    assert "contents: write" not in header
    assert "pull-requests: write" not in header

    assert "actions/create-github-app-token@v2" in text
    assert "app-id: ${{ vars.REQSYS_STACK_REBASE_APP_ID }}" in text
    assert "private-key: ${{ secrets.REQSYS_STACK_REBASE_PRIVATE_KEY }}" in text
    assert "permission-contents: write" in text
    assert "permission-pull-requests: write" not in text
    assert "permission-actions: write" not in text
    assert "permission-issues: write" not in text


def test_reads_use_builtin_token_and_mutation_uses_app_token() -> None:
    text = _text()

    assert "github-token: ${{ github.token }}" in text
    assert "APP_TOKEN: ${{ steps.app-token.outputs.token }}" in text
    assert "GIT_CONFIG_KEY_0: 'http.https://github.com/.extraheader'" in text
    assert "GIT_CONFIG_VALUE_0: 'AUTHORIZATION: basic ' + basicAuth" in text
    assert "GH_PAT_ACTIONS" not in text
    assert "secrets.GITHUB_TOKEN" not in text


def test_app_configuration_fails_closed() -> None:
    text = _text()
    assert 'APP_ID: ${{ vars.REQSYS_STACK_REBASE_APP_ID }}' in text
    assert 'PRIVATE_KEY: ${{ secrets.REQSYS_STACK_REBASE_PRIVATE_KEY }}' in text
    assert "GitHub App governada não configurada." in text


def test_agent_limits_ci_fanout() -> None:
    text = _text()
    assert 'MAX_BRANCH_SYNCS: "3"' in text
    assert "updatesStarted >= maxSyncs" in text
    assert "branch_sync_budget_exhausted" in text


def test_agent_fails_closed_before_sync() -> None:
    text = _text()

    assert "current.head.sha !== expectedHeadSha" in text
    assert "current.mergeable === false" in text
    assert "current.mergeable_state === 'dirty'" in text
    assert "observed.mergeable === null" in text
    assert "external_fork" in text
    assert "draft" in text
    assert "remoteHead !== expectedHeadSha" in text
    assert "remoteBase !== baseSha" in text
    assert "head_changed_before_git_sync" in text
    assert "base_changed_before_git_sync" in text


def test_agent_uses_git_object_merge_and_non_force_push() -> None:
    text = _text()

    assert "git', ['init', '--bare'" in text
    assert "'merge-tree', '--write-tree', expectedHeadSha, baseSha" in text
    assert "'commit-tree', treeSha" in text
    assert "'-p', expectedHeadSha" in text
    assert "'-p', baseSha" in text
    assert "'push', '--porcelain', 'origin'" in text
    assert "newSha + ':refs/heads/' + headBranch" in text
    assert "--force" not in text
    assert "github.rest.pulls.updateBranch" not in text


def test_agent_requires_independent_post_read() -> None:
    text = _text()

    assert "async function confirmSync" in text
    assert "after.head.sha === expectedHeadSha" in text
    assert "basehead: baseSha + '...' + after.head.sha" in text
    assert "afterComparison.behind_by" in text
    assert "post_read_base_not_ancestor" in text
    assert "sync_not_confirmed" in text


def test_agent_never_executes_candidate_code() -> None:
    text = _text()
    self_sync = text.split("sync-current-pr:", maxsplit=1)[1].split(
        "sync-open-prs:", maxsplit=1
    )[0]

    assert "actions/checkout" not in self_sync
    assert "'init', '--bare'" in self_sync
    assert "'checkout'" not in self_sync
    assert "'switch'" not in self_sync


def test_agent_never_integrates_pr_or_deploys() -> None:
    text = _text()

    assert "github.rest.pulls.merge" not in text
    assert "merge_method" not in text
    assert "github.rest.repos.createDeployment" not in text
    assert "fly deploy" not in text.lower()
    assert "newSha + ':refs/heads/main'" not in text
    assert "A sincronização só atualiza a branch head; não integra PR na main" in text


def test_agent_has_scoped_concurrency_lane() -> None:
    text = _text()
    assert "group: repository-governance-agent-" in text
    assert "main-sync" in text
    assert "github.event.pull_request.number" in text
    assert "cancel-in-progress: true" in text


def test_global_sync_only_runs_for_main_push_or_manual_dispatch() -> None:
    text = _text()
    marker = "sync-open-prs:"
    block = text.split(marker, maxsplit=1)[1]
    assert "if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'" in block


def test_self_sync_only_runs_from_pull_request_target() -> None:
    text = _text()
    marker = "sync-current-pr:"
    block = text.split(marker, maxsplit=1)[1].split("sync-open-prs:", maxsplit=1)[0]
    assert "if: github.event_name == 'pull_request_target'" in block
    assert "context.payload.pull_request.number" in block


def test_mutation_failures_are_explicit() -> None:
    text = _text()

    assert "git_push_failed" in text
    assert "invalid_merge_tree_sha" in text
    assert "invalid_merge_commit_sha" in text
    assert "post_read_base_not_ancestor" in text
    assert "sync_not_confirmed" in text
    assert "core.setFailed" in text
