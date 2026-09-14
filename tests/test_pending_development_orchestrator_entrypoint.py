import subprocess
import sys
from pathlib import Path

from scripts.pending_development_orchestrator_entrypoint import (
    issue_source_is_trusted,
    trusted_issue_candidate,
)


def issue(
    *,
    author: str = "external-user",
    title: str = "Pendência comum",
    body: str = "",
    labels: list[str] | None = None,
) -> dict:
    return {
        "number": 42,
        "title": title,
        "body": body,
        "user": {"login": author},
        "labels": [{"name": name} for name in (labels or [])],
    }


def test_entrypoint_executes_from_repository_root() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "scripts/pending_development_orchestrator_entrypoint.py",
            "--help",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Orquestrador governado de desenvolvimento pendente" in result.stdout


def test_external_author_cannot_enable_with_title_only() -> None:
    candidate = issue(title="[AUTO-NEXT] executar desenvolvimento")
    assert not issue_source_is_trusted(candidate, "repo-owner")
    assert not trusted_issue_candidate(
        candidate,
        repo_owner="repo-owner",
        event_name="schedule",
    )


def test_external_author_cannot_enable_with_marker_only() -> None:
    candidate = issue(body="<!-- pending-development-orchestrator:auto -->")
    assert not issue_source_is_trusted(candidate, "repo-owner")


def test_repository_owner_can_enable_with_title() -> None:
    candidate = issue(author="repo-owner", title="[AUTO-NEXT] executar desenvolvimento")
    assert issue_source_is_trusted(candidate, "repo-owner")


def test_github_actions_bot_can_enable_with_marker() -> None:
    candidate = issue(
        author="github-actions[bot]",
        body="<!-- pending-development-orchestrator:auto -->",
    )
    assert issue_source_is_trusted(candidate, "repo-owner")


def test_privileged_auto_label_is_authoritative() -> None:
    candidate = issue(labels=["orchestrator:auto"])
    assert issue_source_is_trusted(candidate, "repo-owner")


def test_issue_event_explicit_selection_does_not_bypass_trust() -> None:
    candidate = issue(title="[AUTO-NEXT] texto externo")
    assert not trusted_issue_candidate(
        candidate,
        repo_owner="repo-owner",
        event_name="issues",
        explicitly_selected=True,
    )


def test_manual_dispatch_explicit_selection_remains_operator_controlled() -> None:
    candidate = issue()
    assert trusted_issue_candidate(
        candidate,
        repo_owner="repo-owner",
        event_name="workflow_dispatch",
        explicitly_selected=True,
    )


def test_pull_request_is_never_issue_candidate() -> None:
    candidate = issue(labels=["orchestrator:auto"])
    candidate["pull_request"] = {"url": "https://api.github.com/example"}
    assert not trusted_issue_candidate(
        candidate,
        repo_owner="repo-owner",
        event_name="schedule",
    )
