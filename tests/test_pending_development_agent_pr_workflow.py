from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/pending-development-agent-pr.yml"
WATCHER_PATH = ROOT / ".github/workflows/pending-development-agent-pr-permission-watch.yml"


def load_yaml(path: Path) -> dict:
    # PyYAML 1.1 interpreta a chave `on` como boolean; BaseLoader preserva o contrato textual.
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def load_workflow() -> dict:
    return load_yaml(WORKFLOW_PATH)


def load_watcher() -> dict:
    return load_yaml(WATCHER_PATH)


def test_agent_pr_waits_for_successful_pre_pr_readiness() -> None:
    workflow = load_workflow()

    assert workflow["on"]["workflow_run"]["workflows"] == ["Pre-PR Readiness Gate"]
    assert workflow["on"]["workflow_run"]["types"] == ["completed"]
    condition = workflow["jobs"]["open-governed-pr"]["if"]
    assert "workflow_run.conclusion == 'success'" in condition
    assert "startsWith(github.event.workflow_run.head_branch, 'copilot/')" in condition


def test_agent_pr_is_bound_to_the_validated_sha_and_branch() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    # Nunca fazer checkout e executar código controlado pela branch do agente
    # em um workflow_run com token capaz de criar PR.
    assert "ref: ${{ github.event.workflow_run.head_sha }}" not in workflow_text
    assert 'GITHUB_SHA: ${{ github.event.workflow_run.head_sha }}' not in workflow_text
    assert '--branch "${{ github.event.workflow_run.head_branch }}"' in workflow_text
    assert '--head-sha "${{ github.event.workflow_run.head_sha }}"' in workflow_text
    assert "READY_FOR_PR_WAIT_SECONDS: \"0\"" in workflow_text


def test_agent_pr_uses_governed_github_app_token() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "actions/create-github-app-token@v2" in workflow_text
    assert "app-id: ${{ vars.REQSYS_STACK_REBASE_APP_ID }}" in workflow_text
    assert "private-key: ${{ secrets.REQSYS_STACK_REBASE_PRIVATE_KEY }}" in workflow_text
    assert "permission-actions: read" in workflow_text
    assert "permission-contents: read" in workflow_text
    assert "permission-pull-requests: write" in workflow_text
    assert "GH_TOKEN: ${{ steps.app-token.outputs.token }}" in workflow_text
    assert "GITHUB_TOKEN:" not in workflow_text


def test_agent_pr_builtin_token_is_read_only() -> None:
    permissions = load_workflow()["permissions"]

    assert permissions == {
        "actions": "read",
        "contents": "read",
    }


def test_permission_watch_is_native_hourly_and_manual() -> None:
    watcher = load_watcher()
    triggers = watcher["on"]

    assert triggers["schedule"] == [{"cron": "23 * * * *"}]
    assert "workflow_dispatch" in triggers
    assert watcher["concurrency"]["cancel-in-progress"] == "false"


def test_permission_watch_requests_exact_minimum_scope() -> None:
    watcher = load_watcher()
    steps = watcher["jobs"]["watch-pr-write"]["steps"]
    token_step = next(step for step in steps if step.get("id") == "app-token")

    assert token_step["uses"] == "actions/create-github-app-token@v2"
    assert token_step["continue-on-error"] == "true"
    assert token_step["with"] == {
        "app-id": "${{ vars.REQSYS_STACK_REBASE_APP_ID }}",
        "private-key": "${{ secrets.REQSYS_STACK_REBASE_PRIVATE_KEY }}",
        "owner": "${{ github.repository_owner }}",
        "repositories": "reqsys-v2-enterprise-real",
        "permission-actions": "read",
        "permission-contents": "read",
        "permission-pull-requests": "write",
    }


def test_permission_watch_is_idempotent_and_self_disabling() -> None:
    watcher = load_watcher()
    watcher_text = WATCHER_PATH.read_text(encoding="utf-8")

    assert watcher["permissions"] == {
        "actions": "write",
        "contents": "read",
        "issues": "write",
    }
    assert "pending-development-agent-pr-permission-ready:issue:1677" in watcher_text
    assert "issues/1677/comments" in watcher_text
    assert "pending-development-agent-pr-permission-watch.yml/disable" in watcher_text
    assert "steps.app-token.outcome == 'success'" in watcher_text
    assert "steps.app-token.outcome != 'success'" in watcher_text
    assert "merge_pull_request" not in watcher_text
