from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "scheduled-operational-watch.yml"


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_monitor_reuses_existing_operational_schedule_without_new_cron() -> None:
    raw = text()
    assert "name: Scheduled Operational Watch" in raw
    assert raw.count("schedule:") == 1
    assert raw.count("cron:") == 1
    assert "cron: '0 */4 * * *'" in raw
    assert "operational-watch:" in raw
    assert "microsoft-graph-planner-teams-watch:" in raw


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
    assert "if (next.rss_initialized && previousWatermark > 0)" in raw
    assert "if (!old) seeded.push(source.id)" in raw
    assert "if (!seen.has(entry.id))" in raw
    assert "Source errors detected; no alert is emitted from errors alone." in raw
    assert "Não conceder permissão automaticamente." in raw
    assert "replay sem duplicidade" in raw
    assert "### Descrição do problema" in raw
    assert "### Estado atual evidenciado" in raw
    assert "### Critérios de aceite" in raw
    assert "### Declaração de rastreabilidade" in raw
    assert "- [x] Issue canônica de estado do monitor" in raw


def test_monitor_uses_minimum_permissions_and_immutable_actions() -> None:
    raw = text()
    assert "contents: read" in raw
    assert "issues: write" in raw
    assert "actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b" in raw
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in raw
    assert "actions/github-script@v" not in raw
    assert "actions/upload-artifact@v" not in raw


def test_manual_graph_watch_dispatch_is_exact_issue_scoped_and_inputless() -> None:
    gateway = (ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml").read_text(
        encoding="utf-8"
    )
    command = "/reqsys run microsoft-graph-planner-teams-watch"
    assert "github.event.issue.number == 1705" in gateway
    assert "github.event.comment.user.login == 'ericson-j-santos'" in gateway
    assert ("github.event.comment.body == '" + command + "'") in gateway
    assert ("'" + command + "')") in gateway
    assert "target='scheduled-operational-watch.yml'" in gateway
    assert "main-post-merge-validation.yml|scheduled-operational-watch.yml|actions-dispatcher.yml" in gateway
    assert "-f graph_watch" not in gateway


def test_rss_replay_uses_watermark_instead_of_truncated_historical_ids() -> None:
    raw = text()
    assert "rss_latest_published_ms" in raw
    assert "rss_recent_ids" in raw
    assert "previousWatermark > 0" in raw
    assert "entry.publishedMs > previousWatermark" in raw
    assert "entry.publishedMs === previousWatermark && !recentIds.has(entry.id)" in raw
    assert "Migration/baseline: seed the current feed without replaying historical entries." in raw
    assert "seen_rss_ids.slice(-200)" not in raw


def test_rss_material_filter_requires_graph_teams_context_for_authentication() -> None:
    raw = text()
    assert "function rssEntryIsMaterial(entry)" in raw
    assert "const appAuthChange = hasAny(authSignals) && hasAny(graphContextSignals);" in raw
    assert "'authentication', 'teams'" not in raw
    assert "'client credential', 'client credentials', 'service principal'" in raw
    assert "'channelmessage.read', 'channelmessage.send'" in raw


def test_rss_state_migration_is_bounded_and_idempotent() -> None:
    raw = text()
    assert "schema_version: '1.1'" in raw
    assert "currentWatermark - (30 * 24 * 60 * 60 * 1000)" in raw
    assert ").slice(0, 200);" in raw
    assert "if (next.rss_initialized && previousWatermark > 0)" in raw
