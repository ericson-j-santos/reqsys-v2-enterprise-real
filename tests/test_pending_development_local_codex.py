from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import local_codex_textonly as textonly
from scripts import pending_development_local_codex as local_codex
from scripts import pending_development_orchestrator as core

BASE_SHA = "a" * 40


def issue(number: int = 1677) -> dict[str, Any]:
    return {
        "number": number,
        "title": "Validar fallback local Codex",
        "body": "<!-- pending-development-orchestrator:auto -->\nTipo de incremento: gap_fix",
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
        return self.comments

    def request(self, method: str, path: str, *, token: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        assert token is None
        self.requests.append((method, path, payload))
        return {}


def agent_blocked(*args, **kwargs) -> core.Decision:
    item = args[1]
    return core.Decision(
        "issue",
        int(item["number"]),
        str(item["title"]),
        "copilot_agent_task_branch_first",
        "blocked",
        "missing_copilot_agent_token",
        "standard",
        "gap_fix",
        "gap_fix_referenciado",
        url=str(item["html_url"]),
    )


def test_missing_agent_token_dispatches_worker_pool_before_marker() -> None:
    client = FakeClient()
    decision = local_codex.process_issue_with_local_fallback(
        client,
        issue(),
        {},
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
        fallback=agent_blocked,
        enabled=True,
        base_sha=BASE_SHA,
    )
    assert decision.route == local_codex.LOCAL_CODEX_ROUTE
    assert decision.status == "dispatched"
    assert decision.action_executed is True
    assert decision.reason.startswith("agent_task_unavailable_worker_pool_dispatched:")
    assert [path for _method, path, _payload in client.requests] == [
        "actions/workflows/codex-worker-pool-handoff.yml/dispatches",
        "issues/1677/comments",
    ]
    dispatch = client.requests[0][2]
    assert dispatch is not None
    assert dispatch["ref"] == "main"
    assert dispatch["inputs"]["base_sha"] == BASE_SHA
    assert dispatch["inputs"]["request_id"] == local_codex.local_codex_request_id("owner/repo", 1677, "main")
    body = str(client.requests[1][2]["body"])
    assert local_codex.local_codex_marker(1677) in body
    assert local_codex.worker_pool_marker(1677) in body
    assert '"create_pull_request": false' in body
    assert '"execution_mode": "branch_first"' in body
    assert '"executor": "codex_worker_pool"' in body


def test_existing_local_and_pool_markers_prevent_duplicate() -> None:
    client = FakeClient()
    client.comments = [{
        "body": (
            local_codex.local_codex_marker(1677)
            + "\n"
            + local_codex.worker_pool_marker(1677)
        )
    }]
    decision = local_codex.process_issue_with_local_fallback(
        client,
        issue(),
        {},
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
        fallback=agent_blocked,
        enabled=True,
        base_sha=BASE_SHA,
    )
    assert decision.status == "already_dispatched"
    assert decision.reason == "local_codex_worker_pool_request_already_present"
    assert client.requests == []


def test_legacy_local_marker_recovers_worker_pool_handoff() -> None:
    client = FakeClient()
    client.comments = [{"body": local_codex.local_codex_marker(1677)}]
    decision = local_codex.process_issue_with_local_fallback(
        client,
        issue(),
        {},
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
        fallback=agent_blocked,
        enabled=True,
        base_sha=BASE_SHA,
    )
    assert decision.status == "dispatched"
    assert decision.action_executed is True
    assert decision.reason.startswith("legacy_local_codex_worker_pool_recovered:")
    assert [path for _method, path, _payload in client.requests] == [
        "actions/workflows/codex-worker-pool-handoff.yml/dispatches",
        "issues/1677/comments",
    ]
    assert local_codex.worker_pool_marker(1677) in str(client.requests[1][2]["body"])


def test_disabled_fallback_preserves_fail_closed() -> None:
    client = FakeClient()
    decision = local_codex.process_issue_with_local_fallback(
        client,
        issue(),
        {},
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
        fallback=agent_blocked,
        enabled=False,
        base_sha=BASE_SHA,
    )
    assert decision.route == "copilot_agent_task_branch_first"
    assert decision.status == "blocked"
    assert client.requests == []


def test_premium_quota_failure_dispatches_worker_pool() -> None:
    client = FakeClient(token="configured")

    def quota_fallback(*args, **kwargs) -> core.Decision:
        item = args[1]
        if kwargs["execute"]:
            raise core.GitHubApiError("GitHub Agent Tasks error 412: insufficient premium quota to create assignment")
        return core.Decision(
            "issue",
            int(item["number"]),
            str(item["title"]),
            "copilot_agent_task_branch_first",
            "planned",
            "eligible_issue_backed_development_branch_first",
            "standard",
            "gap_fix",
            "gap_fix_referenciado",
            url=str(item["html_url"]),
        )

    decision = local_codex.process_issue_with_local_fallback(
        client,
        issue(),
        {},
        execute=True,
        base_branch="main",
        dispatched_routes=set(),
        fallback=quota_fallback,
        enabled=True,
        base_sha=BASE_SHA,
    )
    assert decision.route == local_codex.LOCAL_CODEX_ROUTE
    assert decision.status == "dispatched"
    assert decision.reason.startswith("agent_task_quota_worker_pool_dispatched:")
    assert client.requests[0][1].endswith("/dispatches")


def test_invalid_base_sha_fails_before_marker() -> None:
    client = FakeClient()
    with pytest.raises(core.GitHubApiError, match="GITHUB_SHA inválido"):
        local_codex.process_issue_with_local_fallback(
            client,
            issue(),
            {},
            execute=True,
            base_branch="main",
            dispatched_routes=set(),
            fallback=agent_blocked,
            enabled=True,
            base_sha="bad",
        )
    assert client.requests == []


def test_request_id_is_deterministic() -> None:
    first = local_codex.local_codex_request_id("owner/repo", 1677, "main")
    second = local_codex.local_codex_request_id("owner/repo", 1677, "main")
    assert first == second
    assert len(first) == 24


def test_textonly_requires_real_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "generated", "")

    monkeypatch.setattr(textonly.subprocess, "run", fake_run)
    result = textonly.run_codex_textonly(
        codex_bin=tmp_path / "codex.exe",
        workspace=tmp_path,
        prompt="generate",
        output_relative="docs/out.md",
    )
    assert result["result"] == "CODEX_TEXT_ONLY_FAILED"
    assert result["output_exists"] is False


def test_textonly_success_requires_nonempty_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(args, **kwargs):
        output = Path(args[args.index("--output-last-message") + 1])
        output.write_text("# generated\n", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "generated", "")

    monkeypatch.setattr(textonly.subprocess, "run", fake_run)
    result = textonly.run_codex_textonly(
        codex_bin=tmp_path / "codex.exe",
        workspace=tmp_path,
        prompt="generate",
        output_relative="docs/out.md",
    )
    assert result["result"] == "CODEX_TEXT_ONLY_OK"
    assert result["output_size"] > 0


def test_textonly_blocks_output_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="output fora do workspace"):
        textonly.resolve_output(tmp_path, "../escape.md")
