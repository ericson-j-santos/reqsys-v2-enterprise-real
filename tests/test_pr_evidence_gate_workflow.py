from pathlib import Path

WORKFLOW = Path('.github/workflows/pr-evidence-gate.yml')


def read_workflow() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_pr_evidence_gate_has_router_job_always_active():
    text = read_workflow()

    assert 'name: Evidence Router' in text
    assert 'needs: evidence-router' in text
    assert "needs.evidence-router.outputs.run_gate == 'true'" in text


def test_pr_evidence_gate_keeps_full_wait_window_after_fast_poll_change():
    text = read_workflow()

    assert "MAX_WAIT_SECONDS: '300'" in text
    assert "POLL_SECONDS: '15'" in text
    assert "MAX_WAIT_SECONDS: '45'" not in text
    assert "POLL_SECONDS: '5'" not in text


def test_pr_evidence_gate_lists_artifacts_only_after_gate_passes():
    text = read_workflow()

    assert 'async function listRuns(headSha, includeArtifacts = false)' in text
    assert "if (includeArtifacts && run.status === 'completed')" in text
    assert 'runSummaries = await listRuns(headSha, false);' in text
    assert "if (gate.status === 'passed')" in text
    assert 'const artifactRuns = await listRuns(headSha, true);' in text
    assert 'runSummaries = artifactRuns;' in text

    polling_index = text.index('runSummaries = await listRuns(headSha, false);')
    artifact_index = text.index('const artifactRuns = await listRuns(headSha, true);')
    assert polling_index < artifact_index


def test_pr_evidence_gate_uses_single_page_workflow_lookup():
    text = read_workflow()

    assert 'github.rest.actions.listWorkflowRunsForRepo' in text
    assert 'github.paginate(github.rest.actions.listWorkflowRunsForRepo' not in text
    assert "event: 'pull_request'" in text
    assert 'per_page: 100' in text


def test_pr_evidence_gate_reruns_after_required_workflows_complete():
    text = read_workflow()

    assert 'workflow_run:' in text
    assert 'workflows:' in text
    for workflow_name in (
        'CI — ReqSys v2 Enterprise',
        'Governance Quality Gates',
        'Governança Padrão Ouro',
    ):
        assert workflow_name in text
    assert 'types:\n      - completed' in text


def test_pr_evidence_gate_resolves_pr_from_workflow_run_payload():
    text = read_workflow()

    assert 'const workflowRunPullRequest = context.payload.workflow_run?.pull_requests?.[0];' in text
    assert 'if (workflowRunPullRequest?.number)' in text
    assert 'pull_number: Number(workflowRunPullRequest.number)' in text
    assert 'github.event.workflow_run.head_sha' in text


def test_pr_evidence_gate_skips_workflow_run_without_pull_request():
    text = read_workflow()

    assert 'name: Evidence Router' in text
    assert 'workflow_run_without_pull_request' in text
    assert 'name: Registrar skip seguro sem PR' in text
    assert "if: steps.ctx.outputs.enabled == 'false'" in text
    assert "if: steps.ctx.outputs.enabled == 'true'" in text
    assert '"status": "skipped"' in text
    assert 'PR Evidence Gate skipped safely' in text


def test_pr_evidence_gate_defers_transient_timeout_and_rate_limit():
    text = read_workflow()

    assert "status: 'deferred'" in text
    assert "deferred_reason: 'required_workflows_not_completed_within_wait_window'" in text
    assert "deferred_reason: rateLimited ? 'github_api_rate_limit' : null" in text
    assert 'Evidence build deferred due to GitHub API rate limit.' in text
    assert '[[ "$status" == "passed" || "$status" == "deferred" ]]' in text


def test_pr_evidence_gate_keeps_real_failures_blocking():
    text = read_workflow()

    assert 'Strict workflow failed on current head SHA:' in text
    assert 'Governed workflow failed on current head SHA:' in text
    assert "status: rateLimited ? 'deferred' : 'failed'" in text
    assert 'PR Evidence Gate failed with status:' in text
