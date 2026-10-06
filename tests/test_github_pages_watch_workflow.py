from pathlib import Path


WORKFLOW = Path(".github/workflows/scheduled-operational-watch.yml")


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_github_pages_watch_reuses_existing_scheduled_workflow() -> None:
    text = workflow_text()
    assert "cron: '0 */4 * * *'" in text
    assert "github-pages-pc24x7-watch:" in text
    assert "ISSUE_NUMBER: '2179'" in text


def test_github_pages_watch_uses_only_official_sources() -> None:
    text = workflow_text()
    expected = [
        "https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits",
        "https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site",
        "https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site",
        "https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https",
        "https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/troubleshooting-custom-domains-and-github-pages",
        "https://github.blog/changelog/feed/",
    ]
    for source in expected:
        assert source in text


def test_github_pages_watch_suppresses_false_alerts() -> None:
    text = workflow_text()
    assert "material_filter_negative_self_test_failed" in text
    assert "material_filter_positive_self_test_failed" in text
    assert "if (!oldFacts.length)" in text
    assert "seeded.push(source.id)" in text
    assert "if (changes.length > 0)" in text
    assert "errors alone never emit a change alert" in text


def test_github_pages_watch_publishes_sanitized_evidence() -> None:
    text = workflow_text()
    assert "artifacts/github-pages-pc24x7-watch/report.json" in text
    assert "retention-days: 30" in text
    assert "actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3" in text
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in text


def test_github_pages_watch_keeps_state_issue_governed_and_idempotent() -> None:
    text = workflow_text()
    job = text[text.index("  github-pages-pc24x7-watch:") :]
    required_sections = [
        "### Descrição do problema",
        "### Estado atual evidenciado",
        "### Estado esperado",
        "### Causa raiz",
        "### Critérios de aceite",
        "### Riscos",
        "### Dependências",
        "### Evidências",
        "### PR(s) relacionadas",
        "### Responsável",
        "### Prioridade",
        "### Declaração de rastreabilidade",
    ]
    for section in required_sections:
        assert section in job
    assert "- [x] Issue canônica de estado do monitor GitHub Pages" in job
    assert "if (currentBody.trim() !== nextBody.trim())" in job
    assert "Replay sem mudança não duplica comentário nem reescreve a Issue sem alteração de estado." in job
