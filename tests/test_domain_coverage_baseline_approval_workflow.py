from pathlib import Path


WORKFLOW = Path(".github/workflows/domain-coverage-baseline-approval.yml")


def test_workflow_maintenance_does_not_require_baseline_approval():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'echo "run_gate=true"' not in text
    assert '. == "config/domain-coverage-policy.json"' in text
    assert '. == "docs/ops-dashboard/data/domain-coverage-baseline-diff.json"' in text
    scope = text.split('RUN_GATE="$(gh api', 1)[1].split('echo "run_gate=', 1)[0]
    assert '.github/workflows/domain-coverage-baseline-approval.yml' not in scope


def test_real_baseline_change_remains_human_approved():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'if [[ "${APPROVALS}" -ge 1 ]]' in text
    assert 'EXPECTED="/confirm-domain-baseline ${HEAD_SHA}"' in text
    assert 'test "${CONFIRMATIONS}" -ge 1' in text


def test_scope_router_aggregates_all_pr_pages():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "--paginate --slurp" in text
    assert ".[][] | .filename" in text
    assert "files?per_page=100" in text
    assert "jq -r" in text
