#!/usr/bin/env python3
"""Fallback branch-first para fila local Codex quando GitHub Agent Tasks não pode despachar."""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Callable

from scripts import pending_development_orchestrator as core

LOCAL_CODEX_ROUTE = "local_codex_branch_first"
LOCAL_CODEX_GUARDRAIL = "local_codex_queue_branch_first_fail_closed"
LOCAL_CODEX_MARKER_PREFIX = "<!-- pending-development-orchestrator:local-codex:issue:"
WORKER_POOL_MARKER_PREFIX = "<!-- pending-development-orchestrator:worker-pool:issue:"
WORKER_POOL_WORKFLOW = "codex-worker-pool-handoff.yml"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
_INSTALL_MARKER = "_pending_development_local_codex_installed"


def local_codex_marker(issue_number: int) -> str:
    return f"{LOCAL_CODEX_MARKER_PREFIX}{issue_number} -->"


def worker_pool_marker(issue_number: int) -> str:
    return f"{WORKER_POOL_MARKER_PREFIX}{issue_number} -->"


def local_codex_request_id(repo: str, issue_number: int, base_branch: str) -> str:
    raw = f"{repo}:{issue_number}:{base_branch}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _markers(client: core.GitHubClient, issue_number: int) -> tuple[bool, bool]:
    local = local_codex_marker(issue_number)
    pool = worker_pool_marker(issue_number)
    comments = [str(item.get("body") or "") for item in client.list_comments(issue_number)]
    return any(local in body for body in comments), any(pool in body for body in comments)


def _base_sha(value: str | None = None) -> str:
    candidate = (value or os.getenv("GITHUB_SHA", "")).strip().lower()
    if not SHA40.fullmatch(candidate):
        raise core.GitHubApiError("GITHUB_SHA inválido para handoff local Codex")
    return candidate


def dispatch_worker_pool_handoff(
    client: core.GitHubClient,
    *,
    issue_number: int,
    base_branch: str,
    request_id: str,
    base_sha: str | None = None,
) -> None:
    exact_sha = _base_sha(base_sha)
    run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    correlation_id = f"local-codex-{run_id or request_id}"[:128]
    client.request(
        "POST",
        f"actions/workflows/{WORKER_POOL_WORKFLOW}/dispatches",
        payload={
            "ref": base_branch,
            "inputs": {
                "issue_number": str(issue_number),
                "request_id": request_id,
                "base_branch": base_branch,
                "base_sha": exact_sha,
                "correlation_id": correlation_id,
            },
        },
    )


def _post_worker_pool_marker(
    client: core.GitHubClient,
    *,
    issue_number: int,
    request_id: str,
    recovered: bool,
) -> None:
    state = "recuperado" if recovered else "despachado"
    client.request(
        "POST",
        f"issues/{issue_number}/comments",
        payload={
            "body": (
                f"{worker_pool_marker(issue_number)}\n"
                f"Worker Pool handoff {state} para o request_id `{request_id}`. "
                "O workflow PC24x7 executa fail-closed e comprova replay + leitura independente."
            )
        },
    )


def queue_local_codex(
    client: core.GitHubClient,
    issue: dict[str, Any],
    base_branch: str,
    *,
    base_sha: str | None = None,
) -> str:
    number = int(issue["number"])
    request_id = local_codex_request_id(client.repo, number, base_branch)
    exact_sha = _base_sha(base_sha)
    envelope = {
        "schema_version": "1.1.0",
        "request_id": request_id,
        "repository": client.repo,
        "issue_number": number,
        "base_branch": base_branch,
        "base_sha": exact_sha,
        "execution_mode": "branch_first",
        "create_pull_request": False,
        "executor": "codex_worker_pool",
        "worker_pool_handoff": True,
    }

    # O dispatch ocorre antes do marcador. Se falhar, não há falso "já despachado"
    # e a próxima execução pode tentar novamente.
    dispatch_worker_pool_handoff(
        client,
        issue_number=number,
        base_branch=base_branch,
        request_id=request_id,
        base_sha=exact_sha,
    )
    body = (
        f"{local_codex_marker(number)}\n"
        f"{worker_pool_marker(number)}\n"
        "Pending Development Orchestrator: trabalho encaminhado ao Codex Worker Pool branch-first.\n\n"
        f"```json\n{json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2)}\n```\n\n"
        "Guardrails: sem merge, sem deploy, sem alteração de segredos/permissões; PR somente após READY_FOR_PR=passed."
    )
    client.request("POST", f"issues/{number}/comments", payload={"body": body})
    return request_id


def process_issue_with_local_fallback(
    client: core.GitHubClient,
    issue: dict[str, Any],
    status_report: dict[str, Any],
    *,
    execute: bool,
    base_branch: str,
    dispatched_routes: set[str],
    fallback: Callable[..., core.Decision],
    enabled: bool | None = None,
    base_sha: str | None = None,
) -> core.Decision:
    fallback_enabled = (os.getenv("LOCAL_CODEX_QUEUE_ENABLED", "0") == "1") if enabled is None else enabled
    quota_blocked = False
    try:
        decision = fallback(
            client,
            issue,
            status_report,
            execute=execute,
            base_branch=base_branch,
            dispatched_routes=dispatched_routes,
        )
    except core.GitHubApiError as exc:
        if "premium quota" not in str(exc).lower() or not fallback_enabled:
            raise
        quota_blocked = True
        decision = fallback(
            client,
            issue,
            status_report,
            execute=False,
            base_branch=base_branch,
            dispatched_routes=dispatched_routes,
        )

    agent_route = decision.route == "copilot_agent_task_branch_first"
    missing_token = decision.status == "blocked" and decision.reason == "missing_copilot_agent_token"
    if not execute or not fallback_enabled or not agent_route or not (missing_token or quota_blocked):
        return decision

    number = int(issue["number"])
    request_id = local_codex_request_id(client.repo, number, base_branch)
    local_present, pool_present = _markers(client, number)
    if local_present:
        if not pool_present:
            dispatch_worker_pool_handoff(
                client,
                issue_number=number,
                base_branch=base_branch,
                request_id=request_id,
                base_sha=base_sha,
            )
            _post_worker_pool_marker(
                client,
                issue_number=number,
                request_id=request_id,
                recovered=True,
            )
            return core.Decision(
                "issue",
                number,
                decision.title,
                LOCAL_CODEX_ROUTE,
                "dispatched",
                f"legacy_local_codex_worker_pool_recovered:{request_id}",
                decision.risk,
                decision.increment_type,
                decision.gate_reason,
                True,
                url=decision.url,
            )
        return core.Decision(
            "issue",
            number,
            decision.title,
            LOCAL_CODEX_ROUTE,
            "already_dispatched",
            "local_codex_worker_pool_request_already_present",
            decision.risk,
            decision.increment_type,
            decision.gate_reason,
            url=decision.url,
        )

    request_id = queue_local_codex(client, issue, base_branch, base_sha=base_sha)
    reason = "agent_task_quota_worker_pool_dispatched" if quota_blocked else "agent_task_unavailable_worker_pool_dispatched"
    return core.Decision(
        "issue",
        number,
        decision.title,
        LOCAL_CODEX_ROUTE,
        "dispatched",
        f"{reason}:{request_id}",
        decision.risk,
        decision.increment_type,
        decision.gate_reason,
        True,
        url=decision.url,
    )


def install_local_codex_fallback() -> None:
    if getattr(core, _INSTALL_MARKER, False):
        return
    original_process_issue: Callable[..., core.Decision] = core.process_issue
    original_build_report = core.build_report

    def process_issue(client: core.GitHubClient, issue: dict[str, Any], status_report: dict[str, Any], *, execute: bool, base_branch: str, dispatched_routes: set[str]) -> core.Decision:
        return process_issue_with_local_fallback(
            client,
            issue,
            status_report,
            execute=execute,
            base_branch=base_branch,
            dispatched_routes=dispatched_routes,
            fallback=original_process_issue,
        )

    def build_report(*args: Any, **kwargs: Any) -> dict[str, Any]:
        report = original_build_report(*args, **kwargs)
        guardrails = report.setdefault("guardrails", [])
        if LOCAL_CODEX_GUARDRAIL not in guardrails:
            guardrails.append(LOCAL_CODEX_GUARDRAIL)
        return report

    core.process_issue = process_issue
    core.build_report = build_report
    setattr(core, _INSTALL_MARKER, True)
