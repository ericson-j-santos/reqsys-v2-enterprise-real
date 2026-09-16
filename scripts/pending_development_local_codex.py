#!/usr/bin/env python3
"""Fallback branch-first para fila local Codex quando GitHub Agent Tasks não pode despachar."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable

from scripts import pending_development_orchestrator as core

LOCAL_CODEX_ROUTE = "local_codex_branch_first"
LOCAL_CODEX_GUARDRAIL = "local_codex_queue_branch_first_fail_closed"
LOCAL_CODEX_MARKER_PREFIX = "<!-- pending-development-orchestrator:local-codex:issue:"
_INSTALL_MARKER = "_pending_development_local_codex_installed"


def local_codex_marker(issue_number: int) -> str:
    return f"{LOCAL_CODEX_MARKER_PREFIX}{issue_number} -->"


def local_codex_request_id(repo: str, issue_number: int, base_branch: str) -> str:
    raw = f"{repo}:{issue_number}:{base_branch}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _existing_marker(client: core.GitHubClient, issue_number: int) -> bool:
    marker = local_codex_marker(issue_number)
    return any(marker in str(item.get("body") or "") for item in client.list_comments(issue_number))


def queue_local_codex(client: core.GitHubClient, issue: dict[str, Any], base_branch: str) -> str:
    number = int(issue["number"])
    request_id = local_codex_request_id(client.repo, number, base_branch)
    envelope = {
        "schema_version": "1.0.0",
        "request_id": request_id,
        "repository": client.repo,
        "issue_number": number,
        "base_branch": base_branch,
        "execution_mode": "branch_first",
        "create_pull_request": False,
        "executor": "codex_local_text_only",
    }
    body = (
        f"{local_codex_marker(number)}\n"
        "Pending Development Orchestrator: trabalho enfileirado para executor local Codex branch-first.\n\n"
        f"```json\n{json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2)}\n```\n\n"
        "Guardrails: sem merge, sem deploy, sem alteração de segredos/permissões; PR somente após READY_FOR_PR=passed."
    )
    client.request("POST", f"issues/{number}/comments", payload={"body": body})
    return request_id


def install_local_codex_fallback() -> None:
    if getattr(core, _INSTALL_MARKER, False):
        return
    original_process_issue: Callable[..., core.Decision] = core.process_issue
    original_build_report = core.build_report

    def process_issue(client: core.GitHubClient, issue: dict[str, Any], status_report: dict[str, Any], *, execute: bool, base_branch: str, dispatched_routes: set[str]) -> core.Decision:
        quota_blocked = False
        try:
            decision = original_process_issue(client, issue, status_report, execute=execute, base_branch=base_branch, dispatched_routes=dispatched_routes)
        except core.GitHubApiError as exc:
            if "premium quota" not in str(exc).lower() or os.getenv("LOCAL_CODEX_QUEUE_ENABLED", "0") != "1":
                raise
            quota_blocked = True
            decision = original_process_issue(client, issue, status_report, execute=False, base_branch=base_branch, dispatched_routes=dispatched_routes)

        agent_route = decision.route == "copilot_agent_task_branch_first"
        missing_token = decision.status == "blocked" and decision.reason == "missing_copilot_agent_token"
        fallback_enabled = os.getenv("LOCAL_CODEX_QUEUE_ENABLED", "0") == "1"
        if not execute or not fallback_enabled or not agent_route or not (missing_token or quota_blocked):
            return decision

        number = int(issue["number"])
        if _existing_marker(client, number):
            return core.Decision("issue", number, decision.title, LOCAL_CODEX_ROUTE, "already_dispatched", "local_codex_request_already_present", decision.risk, decision.increment_type, decision.gate_reason, url=decision.url)
        request_id = queue_local_codex(client, issue, base_branch)
        reason = "agent_task_quota_local_codex_queued" if quota_blocked else "agent_task_unavailable_local_codex_queued"
        return core.Decision("issue", number, decision.title, LOCAL_CODEX_ROUTE, "dispatched", f"{reason}:{request_id}", decision.risk, decision.increment_type, decision.gate_reason, True, url=decision.url)

    def build_report(*args: Any, **kwargs: Any) -> dict[str, Any]:
        report = original_build_report(*args, **kwargs)
        guardrails = report.setdefault("guardrails", [])
        if LOCAL_CODEX_GUARDRAIL not in guardrails:
            guardrails.append(LOCAL_CODEX_GUARDRAIL)
        return report

    core.process_issue = process_issue
    core.build_report = build_report
    setattr(core, _INSTALL_MARKER, True)
