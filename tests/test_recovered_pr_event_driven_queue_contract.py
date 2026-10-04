from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

def test_queue_reuses_existing_workflows() -> None:
    agent = read('.github/workflows/repository-governance-agent.yml')
    governed = read('.github/workflows/governed-pr-automation.yml')
    dispatcher = read('.github/workflows/actions-dispatcher.yml')
    assert 'recoveredPulls.slice(0, 1)' in agent
    assert 'markPullRequestReadyForReview' in governed
    assert "workflow_id: 'repository-governance-agent.yml'" in dispatcher

def test_recovered_ready_is_two_phase_and_sha_guarded() -> None:
    governed = read('.github/workflows/governed-pr-automation.yml')
    block = governed.split('auto-merge-after-governed-queue:', 1)[1].split('  governed-pr-check:', 1)[0]
    assert 'currentDraft.head.sha !== triggerHeadSha' in block
    assert 'currentDraftComparison.behind_by > 0' in block
    assert 'markPullRequestReadyForReview' in block
    assert 'Merge: não executado neste ciclo' in block
    assert 'sha: triggerHeadSha' in block
    assert block.index('markPullRequestReadyForReview') < block.index('github.rest.pulls.merge({')

def test_post_merge_checkpoint_advances_queue() -> None:
    dispatcher = read('.github/workflows/actions-dispatcher.yml')
    assert '<!-- reqsys-recovered-queue-checkpoint -->' in dispatcher
    assert 'github.rest.actions.createWorkflowDispatch' in dispatcher
    assert 'repository-governance-agent.yml' in dispatcher
    assert 'TEAMS_WEBHOOK_URL' in dispatcher

def test_queue_keeps_safety_boundaries() -> None:
    agent = read('.github/workflows/repository-governance-agent.yml')
    governed = read('.github/workflows/governed-pr-automation.yml')
    assert '--force' not in agent
    assert 'github.rest.pulls.merge' not in agent
    assert "merge_method: 'squash'" in governed

def test_persistent_blocker_is_checkpointed_and_notified_without_fly() -> None:
    notify = read('.github/workflows/notify-teams-reqsys-logs.yml')
    assert '- PR CI Watch' in notify
    assert '<!-- reqsys-recovered-queue-blocked -->' in notify
    assert 'ci:recuperado' in notify
    assert 'TEAMS_GATEWAY_BASE_URL: ""' in notify
    assert 'false &&' not in notify
    assert 'reqsys-api.fly.dev' not in notify
    assert 'REQSYS_LOG_STRICT: "true"' in notify

def test_deterministic_technical_failure_reuses_ollama_worker_pool_on_same_pr_branch() -> None:
    workflow = read('.github/workflows/ollama-ci-triage.yml')
    script = read('scripts/ollama_ci_triage.py')

    assert '"CI — ReqSys v2 Enterprise"' in workflow
    assert '"CI Enterprise Fast"' in workflow
    assert "MODE: ${{ github.event_name == 'workflow_run' && 'execute' || inputs.mode }}" in workflow
    assert 'target_branch' in script
    assert 'base_sha' in script
    assert 'same_repository' in script
    assert 'sha_current' in script
    assert 'enqueue_worker_pool' in script
    assert 'DETERMINISTIC_TECHNICAL_CATEGORIES' in script
    assert 'DETERMINISTIC_BLOCKED_CATEGORIES' in script
