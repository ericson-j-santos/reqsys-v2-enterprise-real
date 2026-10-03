from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/teams-recipient-policy-runtime-readiness.yml")


def test_issue_reconciliation_is_fail_closed_and_non_pr_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "issues: write" in text
    assert "all_policies_ready" in text
    assert "issues/1112" in text
    assert "state_reason=completed" in text
    assert "github.event_name != 'pull_request'" in text
    assert "dry-run" in text
    assert "production_touched=false" in text
