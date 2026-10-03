from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "teams-notification-dashboard.yml"


def test_dashboard_runs_after_governed_merge_automation_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_run:" in text
    assert "- Governed PR Automation" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event == 'workflow_run'" in text


def test_dashboard_binds_generated_state_to_checked_out_sha() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'source_sha="$(git rev-parse HEAD)"' in text
    assert "--source-sha" in text
    assert "steps.source.outputs.sha" in text


def test_dashboard_post_merge_trigger_does_not_enable_deploy() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "actions/deploy-pages@" not in text
    assert "pages: write" not in text
    assert "contents: write" not in text
