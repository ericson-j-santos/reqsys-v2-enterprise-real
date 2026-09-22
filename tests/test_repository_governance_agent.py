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


def test_builtin_token_is_read_only_and_app_token_is_minimum_write_scope() -> None:
    text = _text()
    header = text.split("jobs:", maxsplit=1)[0]
    assert "permissions:\n  contents: read\n  pull-requests: read" in header
    assert "pull-requests: write" not in header
    assert "actions/create-github-app-token@v2" in text
    assert "app-id: ${{ vars.REQSYS_STACK_REBASE_APP_ID }}" in text
    assert "private-key: ${{ secrets.REQSYS_STACK_REBASE_PRIVATE_KEY }}" in text
    assert "permission-contents: write" in text
    assert "permission-pull-requests: write" in text
    assert "permission-actions: write" not in text
    assert "permission-issues: write" not in text


def test_mutations_use_app_token_without_native_or_pat_fallback() -> None:
    text = _text()
    assert "github-token: ${{ steps.app-token.outputs.token }}" in text
    assert "GH_PAT_ACTIONS" not in text
    assert "github.token" not in text
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
    assert "actions/checkout" not in block


def test_self_sync_defers_write_token_until_mutation_is_needed() -> None:
    text = _text()
    block = text.split("sync-current-pr:", maxsplit=1)[1].split(
        "sync-open-prs:", maxsplit=1
    )[0]
    assert "Inspecionar necessidade de sincronização" in block
    assert "result-encoding: string" in block
    assert "comparison.behind_by" in block
    assert "credencial de escrita não será emitida" in block
    assert block.index("Inspecionar necessidade de sincronização") < block.index(
        "Validar configuração da GitHub App"
    )
    assert block.count("if: steps.sync-check.outputs.result == 'true'") == 3


def test_global_sync_defers_write_token_when_there_is_no_stale_eligible_pr() -> None:
    text = _text()
    block = text.split("sync-open-prs:", maxsplit=1)[1]
    assert "Inspecionar PRs que podem exigir sincronização" in block
    assert "result-encoding: string" in block
    assert "comparison.behind_by" in block
    assert "Nenhuma PR elegível está atrasada" in block
    assert block.index("Inspecionar PRs que podem exigir sincronização") < block.index(
        "Validar configuração da GitHub App"
    )
    assert block.count("if: steps.sync-scan.outputs.result == 'true'") == 3


def test_mutation_api_errors_fail_the_job() -> None:
    text = _text()
    assert "update_branch_api_" in text
    assert "mutationFailures" in text
    assert "core.setFailed" in text
