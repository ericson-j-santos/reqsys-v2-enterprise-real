from pathlib import Path

WORKFLOW = Path('.github/workflows/close-duplicate-prs.yml')


def test_close_duplicate_prs_workflow_contract():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'name: Close Duplicate PRs' in text
    assert 'workflow_dispatch:' in text
    assert 'pull-requests: write' in text
    assert "core.getInput('canonical_pr')" in text
    assert 'github.rest.pulls.update' in text
    assert 'close-duplicate-prs-evidence' in text
