from pathlib import Path

from scripts.audit_hitl_decision_consistency import audit_issues


def comment(command: str, number: int, author: str = "human") -> dict:
    return {
        "body": f"/{command} justificativa suficientemente longa",
        "url": f"https://github.com/example/repo/issues/1#issuecomment-{number}",
        "createdAt": f"2026-07-31T12:0{number}:00Z",
        "author": {"login": author},
    }


def issue(comments: list[dict]) -> dict:
    return {
        "number": 1,
        "title": "[HITL][BACEN-01] Aprovar politica",
        "url": "https://github.com/example/repo/issues/1",
        "comments": comments,
    }


def test_accepts_single_terminal_decision() -> None:
    report = audit_issues([issue([comment("approve", 1)])])
    assert report["decision"] == "consistent"
    assert report["items"][0]["state"] == "terminal_decision_recorded"


def test_detects_contradictory_terminal_decisions() -> None:
    report = audit_issues([issue([comment("approve", 1), comment("reject", 2)])])
    assert report["decision"] == "review_required"
    assert report["summary"]["conflicts"] == 1
    assert report["items"][0]["state"] == "contradictory_terminal_decisions"


def test_ignores_bot_commands() -> None:
    report = audit_issues([issue([comment("approve", 1, "github-actions[bot]")])])
    assert report["items"][0]["state"] == "no_decision"


def test_detects_duplicate_terminal_decision() -> None:
    report = audit_issues([issue([comment("approve", 1), comment("approve", 2)])])
    assert report["items"][0]["state"] == "duplicate_terminal_decision"


def test_workflow_collects_hitl_issues_without_mutually_exclusive_labels() -> None:
    workflow = Path(".github/workflows/hitl-decision-consistency-guard.yml").read_text(
        encoding="utf-8"
    )
    assert "--search 'HITL in:title'" in workflow
    assert "--label hitl-approval-request,hitl-approved" not in workflow
    assert '"--paginate",' in workflow
    assert '"--slurp",' in workflow
