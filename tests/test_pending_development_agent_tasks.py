from __future__ import annotations

from typing import Any

from scripts import pending_development_agent_tasks as agent_tasks
from scripts import pending_development_orchestrator as core


def issue(number: int = 501) -> dict[str, Any]:
    return {
        "number": number,
        "title": "Implementar ajuste governado",
        "body": "<!-- pending-development-orchestrator:auto -->\nAplicar a menor correção com testes.",
        "labels": [],
        "assignees": [],
        "html_url": f"https://github.example/issues/{number}",
    }


class FakeClient:
    def __init__(self, *, token: str = "") -> None:
        self.repo = "owner/repo"
        self.copilot_token = token
        self.comments: list[dict[str, Any]] = []
        self.requests: list[tuple[str, str, dict[str, Any] | None]] = []

    def list_comments(self, number: int, *, use_copilot_token: bool = False) -> list[dict[str, Any]]:
        assert number > 0
        assert use_copilot_token is False
        return self.comments

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert token is None
        self.requests.append((method, path, payload))
        return {}


def development_fallback(
    client: FakeClient,
    item: dict[str, Any],
    status_report: dict[str, Any],
    *,
    execute: bool,
    base_branch: str,
    dispatched_routes: set[str],
) -> core.Decision:
    del client, status_report, execute, base_branch, dispatched_routes
    return core.Decision(
        "issue",
        int(item["number"]),
        str(item["title"]),
        "copilot_issue_agent",
        "planned",
        "eligible_issue_backed_development",
        "standard",
        "gap_fix",
        "allowed",
        url=str(item["html_url"]),
    )


def test_agent_task_payload_never_creates_pull_request() -> None:
    payload = agent_tasks.build_agent_task_payload("main", "corrigir")

    assert payload == {
        "prompt": "corrigir",
        "create_pull_request": False,
        "base_ref": "main",
    }
    assert agent_tasks.AGENT_TASK_API_VERSION == "2026-03-10"
    assert agent_tasks.agent_task_endpoint("owner/repo") == "https://api.github.com/agents/repos/owner/repo/tasks"


def test_agent_task_instructions_preserve_ready_for_pr_boundary() -> None:
    instructions = agent_tasks.build_agent_task_instructions(issue(), "main")

    assert agent_tasks.agent_task_marker(501) in instructions
    assert "Não abra Pull Request" in instructions
    assert "READY_FOR_PR=passed" in instructions
    assert "Base esperada: main" in instructions


def test_missing_agent_task_token_is_fail_closed() -> None:
    client = FakeClient()

    decision = agent_tasks.process_issue_branch_first(
        client,
        issue(),
        {},
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
        fallback=development_fallback,
    )

    assert decision.route == agent_tasks.AGENT_TASK_ROUTE
    assert decision.status == "blocked"
    assert decision.reason == "missing_copilot_agent_task_token"
    assert decision.action_executed is False
    assert client.requests == []


def test_branch_first_task_is_dispatched_and_audited(monkeypatch) -> None:
    client = FakeClient(token="configured-user-token")
    captured: dict[str, str] = {}

    def fake_start(fake_client: FakeClient, base_branch: str, instructions: str) -> dict[str, str]:
        assert fake_client is client
        assert base_branch == "main"
        assert "Não abra Pull Request" in instructions
        captured["instructions"] = instructions
        return {"id": "task-123", "html_url": "https://github.example/copilot/tasks/task-123"}

    monkeypatch.setattr(agent_tasks, "start_agent_task", fake_start)

    decision = agent_tasks.process_issue_branch_first(
        client,
        issue(),
        {},
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
        fallback=development_fallback,
    )

    assert decision.route == agent_tasks.AGENT_TASK_ROUTE
    assert decision.status == "dispatched"
    assert decision.action_executed is True
    assert captured["instructions"]
    assert len(client.requests) == 1
    method, path, payload = client.requests[0]
    assert method == "POST"
    assert path == "issues/501/comments"
    assert payload is not None
    assert agent_tasks.agent_task_marker(501) in str(payload["body"])
    assert "task-123" in str(payload["body"])
    assert "READY_FOR_PR=passed" in str(payload["body"])


def test_existing_marker_prevents_duplicate_agent_task(monkeypatch) -> None:
    client = FakeClient(token="configured-user-token")
    client.comments = [{"body": agent_tasks.agent_task_marker(501)}]
    called = False

    def should_not_start(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Agent Task duplicada")

    monkeypatch.setattr(agent_tasks, "start_agent_task", should_not_start)

    decision = agent_tasks.process_issue_branch_first(
        client,
        issue(),
        {},
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
        fallback=development_fallback,
    )

    assert decision.status == "already_dispatched"
    assert decision.reason == "agent_task_marker_already_present"
    assert decision.action_executed is False
    assert called is False
    assert client.requests == []


def test_audit_mode_plans_branch_first_without_external_effect() -> None:
    client = FakeClient(token="configured-user-token")

    decision = agent_tasks.process_issue_branch_first(
        client,
        issue(),
        {},
        execute=False,
        base_branch="main",
        dispatched_routes=set(),
        fallback=development_fallback,
    )

    assert decision.route == agent_tasks.AGENT_TASK_ROUTE
    assert decision.status == "planned"
    assert decision.action_executed is False
    assert client.requests == []


def test_non_development_route_is_delegated_unchanged() -> None:
    client = FakeClient(token="configured-user-token")
    calls: list[bool] = []

    def human_gate_fallback(
        fake_client: FakeClient,
        item: dict[str, Any],
        status_report: dict[str, Any],
        *,
        execute: bool,
        base_branch: str,
        dispatched_routes: set[str],
    ) -> core.Decision:
        del fake_client, status_report, base_branch, dispatched_routes
        calls.append(execute)
        return core.Decision(
            "issue",
            int(item["number"]),
            str(item["title"]),
            "human_gate",
            "blocked",
            "sensitive_hint:senha",
            "high",
            "gap_fix",
            "allowed",
            url=str(item["html_url"]),
        )

    decision = agent_tasks.process_issue_branch_first(
        client,
        issue(),
        {},
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
        fallback=human_gate_fallback,
    )

    assert decision.route == "human_gate"
    assert decision.status == "blocked"
    assert calls == [False, True]
