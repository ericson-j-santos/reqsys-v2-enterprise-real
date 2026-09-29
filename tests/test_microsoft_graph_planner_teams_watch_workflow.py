from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "microsoft-graph-planner-teams-watch.yml"


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_monitor_reuses_existing_operational_schedule_without_new_cron() -> None:
    raw = text()
    assert "workflow_run:" in raw
    assert "Scheduled Operational Watch" in raw
    assert "schedule:" not in raw
    assert "cron:" not in raw


def test_monitor_scopes_to_official_graph_surfaces_and_state_issue() -> None:
    raw = text()
    assert "ISSUE_NUMBER: '2165'" in raw
    assert "learn.microsoft.com/en-us/graph/permissions-reference" in raw
    assert "channel-list-messages?view=graph-rest-1.0" in raw
    assert "chatmessage-post?view=graph-rest-1.0" in raw
    assert "teams-changenotifications-chatmessage" in raw
    assert "resource-specific-consent" in raw
    assert "developer.microsoft.com/en-us/graph/changelog/rss" in raw
    assert "ChannelMessage.Read.Group" in raw
    assert "ChannelMessage.Read.All" in raw
    assert "ChannelMessage.Send.Group" in raw
    assert "Teamwork.Migrate.All" in raw


def test_monitor_is_fail_closed_for_alerts_and_idempotent() -> None:
    raw = text()
    assert "if (changes.length)" in raw
    assert "if (next.rss_initialized)" in raw
    assert "if (!old) seeded.push(source.id)" in raw
    assert "if (!seen.has(entry.id))" in raw
    assert "Source errors detected; no alert is emitted from errors alone." in raw
    assert "Não conceder permissão automaticamente." in raw
    assert "replay sem duplicidade" in raw


def test_monitor_uses_minimum_permissions_and_immutable_actions() -> None:
    raw = text()
    assert "contents: read" in raw
    assert "issues: write" in raw
    assert "actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b" in raw
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in raw
    assert "actions/github-script@v" not in raw
    assert "actions/upload-artifact@v" not in raw
