from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.pr_quality_review import ChangedFile, PullRequestContext, classify_risk  # noqa: E402
import pr_quality_review_entry  # noqa: E402


def pr_context(draft: bool = False) -> PullRequestContext:
    return PullRequestContext(
        repo="ericson-j-santos/reqsys-v2-enterprise-real",
        pr_number="145",
        title="chore(ci): replace CodeRabbit with PR Quality Review",
        state="open",
        draft=draft,
        head_sha="abc123",
        base_ref="main",
        html_url="https://example.local/pr/145",
    )


def changed_file(filename: str, changes: int = 10) -> ChangedFile:
    return ChangedFile(
        filename=filename,
        status="modified",
        additions=changes,
        deletions=0,
        changes=changes,
    )


def governed_changed_file(filename: str, changes: int = 10):
    return pr_quality_review_entry.review.ChangedFile(
        filename=filename,
        status="modified",
        additions=changes,
        deletions=0,
        changes=changes,
    )


def test_classify_workflow_change_warns_without_critical_block() -> None:
    severity, score, findings = classify_risk(
        [changed_file(".github/workflows/pr-quality-review.yml")],
        pr_context(),
    )

    assert severity == "warning"
    assert score < 100
    assert any(finding.category == "ci_cd" for finding in findings)
    assert not any(finding.severity == "critical" for finding in findings)


def test_classify_sensitive_filename_blocks() -> None:
    severity, score, findings = classify_risk(
        [changed_file("config/private_key_placeholder.txt")],
        pr_context(),
    )

    assert severity == "critical"
    assert score <= 50
    assert any(finding.category == "seguranca" for finding in findings)


def test_governed_classifier_allows_public_figma_token_artifact() -> None:
    artifact = governed_changed_file("frontend/artifacts/figma-tokens/reqsys.tokens.json")

    assert artifact.is_sensitive is False


def test_governed_classifier_keeps_real_token_config_sensitive() -> None:
    token_config = governed_changed_file("config/access-token.json")

    assert token_config.is_sensitive is True


def test_classify_docs_only_ok() -> None:
    severity, score, findings = classify_risk(
        [changed_file("docs/adr/ADR-0024-substituicao-coderabbit-pr-quality-review.md")],
        pr_context(),
    )

    assert severity == "ok"
    assert score == 100
    assert findings == []
