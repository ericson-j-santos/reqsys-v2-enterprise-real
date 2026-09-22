import os
import subprocess
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


def _git(cwd: Path, *args: str, check: bool = True, env: dict[str, str] | None = None):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed with {result.returncode}: "
            f"{result.stdout}\n{result.stderr}"
        )
    return result


def _commit_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "reqsys-repository-governance[bot]",
            "GIT_AUTHOR_EMAIL": "actions@github.com",
            "GIT_COMMITTER_NAME": "reqsys-repository-governance[bot]",
            "GIT_COMMITTER_EMAIL": "actions@github.com",
        }
    )
    return env


def _build_sync_commit(
    worker: Path, expected_head_sha: str, base_sha: str, message: str
) -> str:
    merge_tree = _git(
        worker,
        "merge-tree",
        "--write-tree",
        expected_head_sha,
        base_sha,
    ).stdout.strip().splitlines()[0]
    return _git(
        worker,
        "commit-tree",
        merge_tree,
        "-p",
        expected_head_sha,
        "-p",
        base_sha,
        "-m",
        message,
        env=_commit_env(),
    ).stdout.strip()


def test_git_object_sync_smoke_and_concurrent_push_is_rejected(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare")

    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init")
    _git(seed, "config", "user.name", "test-user")
    _git(seed, "config", "user.email", "test@example.com")
    _git(seed, "branch", "-M", "main")
    (seed / "base.txt").write_text("base\n", encoding="utf-8")
    _git(seed, "add", "base.txt")
    _git(seed, "commit", "-m", "base")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-u", "origin", "main")

    _git(seed, "switch", "-c", "feature")
    (seed / "feature.txt").write_text("feature\n", encoding="utf-8")
    _git(seed, "add", "feature.txt")
    _git(seed, "commit", "-m", "feature")
    feature_sha = _git(seed, "rev-parse", "HEAD").stdout.strip()
    _git(seed, "push", "-u", "origin", "feature")

    _git(seed, "switch", "main")
    (seed / "main.txt").write_text("main advanced\n", encoding="utf-8")
    _git(seed, "add", "main.txt")
    _git(seed, "commit", "-m", "main advanced")
    base_sha = _git(seed, "rev-parse", "HEAD").stdout.strip()
    _git(seed, "push", "origin", "main")

    worker = tmp_path / "worker.git"
    worker.mkdir()
    _git(worker, "init", "--bare")
    _git(worker, "remote", "add", "origin", str(remote))
    _git(
        worker,
        "fetch",
        "--no-tags",
        "origin",
        "+refs/heads/main:refs/remotes/origin/main",
        "+refs/heads/feature:refs/remotes/origin/feature",
    )
    assert _git(worker, "rev-parse", "refs/remotes/origin/feature").stdout.strip() == feature_sha
    assert _git(worker, "rev-parse", "refs/remotes/origin/main").stdout.strip() == base_sha

    sync_sha = _build_sync_commit(worker, feature_sha, base_sha, "sync feature with main")
    _git(worker, "push", "origin", f"{sync_sha}:refs/heads/feature")

    assert _git(remote, "rev-parse", "refs/heads/feature").stdout.strip() == sync_sha
    assert _git(remote, "merge-base", "--is-ancestor", base_sha, sync_sha).returncode == 0
    parents = _git(worker, "show", "-s", "--format=%P", sync_sha).stdout.strip().split()
    assert parents == [feature_sha, base_sha]

    _git(seed, "branch", "feature-race", feature_sha)
    _git(seed, "push", "origin", "feature-race")

    race_worker = tmp_path / "race-worker.git"
    race_worker.mkdir()
    _git(race_worker, "init", "--bare")
    _git(race_worker, "remote", "add", "origin", str(remote))
    _git(
        race_worker,
        "fetch",
        "--no-tags",
        "origin",
        "+refs/heads/main:refs/remotes/origin/main",
        "+refs/heads/feature-race:refs/remotes/origin/feature-race",
    )
    race_sync_sha = _build_sync_commit(
        race_worker,
        feature_sha,
        base_sha,
        "sync raced feature with main",
    )

    _git(seed, "switch", "feature-race")
    (seed / "concurrent.txt").write_text("concurrent\n", encoding="utf-8")
    _git(seed, "add", "concurrent.txt")
    _git(seed, "commit", "-m", "concurrent advance")
    concurrent_sha = _git(seed, "rev-parse", "HEAD").stdout.strip()
    _git(seed, "push", "origin", "feature-race")

    rejected = _git(
        race_worker,
        "push",
        "origin",
        f"{race_sync_sha}:refs/heads/feature-race",
        check=False,
    )
    assert rejected.returncode != 0
    assert _git(remote, "rev-parse", "refs/heads/feature-race").stdout.strip() == concurrent_sha
