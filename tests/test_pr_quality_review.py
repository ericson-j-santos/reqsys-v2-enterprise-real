from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.pr_quality_review import ChangedFile, PullRequestContext, classify_risk  # noqa: E402


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


def test_classify_docs_only_ok() -> None:
    severity, score, findings = classify_risk(
        [changed_file("docs/adr/ADR-0024-substituicao-coderabbit-pr-quality-review.md")],
        pr_context(),
    )

    assert severity == "ok"
    assert score == 100
    assert findings == []
