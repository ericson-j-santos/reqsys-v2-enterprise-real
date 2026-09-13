from __future__ import annotations

from pathlib import Path

from scripts.pending_development_orchestrator import (
    AUTO_MARKER,
    Decision,
    build_report,
    classify_risk,
    copilot_fix_marker,
    failing_runs_for_pr,
    is_issue_candidate,
    pr_is_candidate,
    process_issue,
    process_pr,
)

ROOT = Path(__file__).resolve().parents[1]


def green_status() -> dict:
    return {
        "state": "green",
        "increment_gate": {
            "new_front_allowed": True,
            "allowed_increment_types": [
                "new_front",
                "gap_fix",
                "close_duplicate",
                "hotfix",
                "consolidate",
            ],
            "blockers": [],
            "critical_gaps": 0,
        },
        "automatic_backlog": [],
        "sources": {"watchdog": {"duplicate_pr_numbers": []}},
    }


class FakeClient:
    def __init__(self, *, copilot_token: str = "") -> None:
        self.copilot_token = copilot_token
        self.dispatched = 0
        self.assigned: list[int] = []
        self.pr_fix_requests: list[tuple[int, str]] = []
        self.runs: list[dict] = []
        self.comments: list[dict] = []

    def dispatch_auto_operator(self, base_branch: str) -> None:
        assert base_branch == "main"
        self.dispatched += 1

    def assign_copilot(self, number: int, base_branch: str, instructions: str) -> None:
        assert base_branch == "main"
        assert "Pre-PR Readiness Gate" in instructions
        self.assigned.append(number)

    def list_pr_runs(self, head_sha: str) -> list[dict]:
        assert head_sha
        return self.runs

    def list_comments(self, number: int, *, use_copilot_token: bool = False) -> list[dict]:
        assert number > 0
        return self.comments

    def ask_copilot_to_fix_pr(self, number: int, head_sha: str, failing_runs: list[dict]) -> None:
        assert failing_runs
        self.pr_fix_requests.append((number, head_sha))


def issue(number: int = 101, *, title: str = "Implementar painel", body: str = AUTO_MARKER, labels=None, assignees=None) -> dict:
    return {
        "number": number,
        "title": title,
        "body": body,
        "labels": labels or [],
        "assignees": assignees or [],
        "html_url": f"https://github.example/issues/{number}",
    }


def pull(number: int = 202, *, title: str = "fix: corrigir backend", labels=None) -> dict:
    return {
        "number": number,
        "title": title,
        "body": "",
        "labels": labels or [],
        "html_url": f"https://github.example/pull/{number}",
        "head": {"ref": "copilot/fix-backend", "sha": "abc123"},
    }


def test_issue_candidate_requires_marker_label_or_explicit_selection() -> None:
    assert is_issue_candidate(issue()) is True
    assert is_issue_candidate(issue(body="")) is False
    assert is_issue_candidate(issue(body="", labels=[{"name": "orchestrator:auto"}])) is True
    assert is_issue_candidate(issue(body="", title="[AUTO-NEXT] Incremento")) is True
    assert is_issue_candidate(issue(body=""), explicitly_selected=True) is True


def test_sensitive_work_is_fail_closed_to_human_gate() -> None:
    risk, reason = classify_risk(issue(title="Deploy produção e alterar Key Vault"))
    assert risk == "high"
    assert reason.startswith("sensitive_hint:")


def test_ci_issue_reuses_actions_auto_operator() -> None:
    client = FakeClient()
    decision = process_issue(
        client,
        issue(title="Corrigir falha no CI workflow"),
        green_status(),
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
    )
    assert decision.route == "actions_auto_operator"
    assert decision.status == "dispatched"
    assert decision.action_executed is True
    assert client.dispatched == 1


def test_issue_development_routes_to_copilot_agent() -> None:
    client = FakeClient(copilot_token="configured")
    decision = process_issue(
        client,
        issue(),
        green_status(),
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
    )
    assert decision.route == "copilot_issue_agent"
    assert decision.status == "dispatched"
    assert client.assigned == [101]


def test_missing_copilot_token_blocks_instead_of_false_success() -> None:
    client = FakeClient()
    decision = process_issue(
        client,
        issue(),
        green_status(),
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
    )
    assert decision.status == "blocked"
    assert decision.reason == "missing_copilot_agent_token"
    assert decision.action_executed is False


def test_copilot_assignment_is_idempotent_for_issue() -> None:
    client = FakeClient(copilot_token="configured")
    item = issue(assignees=[{"login": "copilot-swe-agent[bot]"}])
    decision = process_issue(
        client,
        item,
        green_status(),
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
    )
    assert decision.status == "already_dispatched"
    assert client.assigned == []


def test_pull_from_copilot_is_candidate_for_same_pr_remediation() -> None:
    assert pr_is_candidate(pull()) is True
    other = pull()
    other["head"]["ref"] = "feature/human"
    assert pr_is_candidate(other) is False
    other["labels"] = [{"name": "orchestrator:auto-fix"}]
    assert pr_is_candidate(other) is True


def test_deterministic_pr_failure_requests_copilot_fix_on_same_pr() -> None:
    client = FakeClient(copilot_token="configured")
    client.runs = [
        {
            "name": "CI Enterprise Fast",
            "status": "completed",
            "conclusion": "failure",
            "created_at": "2026-09-13T18:00:00Z",
        }
    ]
    decision = process_pr(
        client,
        pull(),
        green_status(),
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
    )
    assert decision is not None
    assert decision.route == "copilot_same_pr_fix"
    assert decision.status == "dispatched"
    assert client.pr_fix_requests == [(202, "abc123")]


def test_transient_pr_failure_uses_rerun_operator() -> None:
    client = FakeClient(copilot_token="configured")
    client.runs = [
        {
            "name": "CI Enterprise Fast",
            "status": "completed",
            "conclusion": "timed_out",
            "created_at": "2026-09-13T18:00:00Z",
        }
    ]
    decision = process_pr(
        client,
        pull(),
        green_status(),
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
    )
    assert decision is not None
    assert decision.route == "actions_auto_operator"
    assert client.dispatched == 1
    assert client.pr_fix_requests == []


def test_same_head_is_not_requested_twice() -> None:
    client = FakeClient(copilot_token="configured")
    client.runs = [
        {
            "name": "CI Enterprise Fast",
            "status": "completed",
            "conclusion": "failure",
            "created_at": "2026-09-13T18:00:00Z",
        }
    ]
    client.comments = [{"body": copilot_fix_marker("abc123")}]
    decision = process_pr(
        client,
        pull(),
        green_status(),
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
    )
    assert decision is not None
    assert decision.status == "already_dispatched"
    assert client.pr_fix_requests == []


def test_report_exposes_blocked_without_claiming_dispatch() -> None:
    decisions = [
        Decision(
            kind="issue",
            number=1,
            title="x",
            route="human_gate",
            status="blocked",
            reason="sensitive",
            risk="high",
        )
    ]
    report = build_report("owner/repo", "main", "execute", "corr-1", decisions)
    assert report["summary"]["blocked"] == 1
    assert report["summary"]["dispatched"] == 0


def test_workflow_is_scheduled_event_driven_and_fail_closed() -> None:
    workflow = (ROOT / ".github/workflows/pending-development-orchestrator.yml").read_text(encoding="utf-8")
    assert 'cron: "41 * * * *"' in workflow
    assert "issues:" in workflow
    assert "types: [opened, reopened, labeled]" in workflow
    assert "startsWith(github.event.issue.title, '[AUTO-NEXT]')" in workflow
    assert "pending-development-orchestrator:auto" in workflow
    assert "orchestrator:auto" in workflow
    assert "github.event.issue.number" in workflow
    assert "github.event_name == 'issues' && 'execute'" in workflow
    assert "COPILOT_AGENT_TOKEN" in workflow
    assert "MODE=\"execute\"" in workflow
    assert "Falhar fechado quando execução estiver bloqueada" in workflow


def test_autonomous_delivery_cycle_materializes_next_increment_issue() -> None:
    workflow = (ROOT / ".github/workflows/autonomous-delivery-cycle.yml").read_text(encoding="utf-8")
    assert "pending-development-orchestrator:auto" in workflow
    assert "queued_for_orchestrator" in workflow
    assert "issues.create" in workflow
    assert "next_increment_issue_materialization_only_after_successful_merge" in workflow


def test_failure_classification_prefers_latest_run_per_workflow() -> None:
    failures, transient = failing_runs_for_pr(
        [
            {
                "name": "CI",
                "status": "completed",
                "conclusion": "failure",
                "created_at": "2026-09-13T17:00:00Z",
            },
            {
                "name": "CI",
                "status": "completed",
                "conclusion": "success",
                "created_at": "2026-09-13T18:00:00Z",
            },
        ]
    )
    assert failures == []
    assert transient == []
