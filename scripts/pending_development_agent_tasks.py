#!/usr/bin/env python3
"""Adaptador branch-first para desenvolvimento de issues via GitHub Agent Tasks.

A rota preserva a governança ReqSys: a tarefa do agente é criada com
``create_pull_request=false``. Assim, implementação e testes podem ocorrer em
branch antes do Pre-PR Readiness Gate; a PR só deve ser aberta depois de
``READY_FOR_PR=passed`` pelo fluxo canônico.
"""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts import pending_development_orchestrator as core

AGENT_TASK_API_VERSION = "2026-03-10"
AGENT_TASK_ROUTE = "copilot_agent_task_branch_first"
AGENT_TASK_GUARDRAIL = "agent_task_create_pull_request_false_before_ready_for_pr"
_INSTALL_MARKER = "_pending_development_agent_tasks_installed"


def agent_task_marker(issue_number: int) -> str:
    return f"<!-- pending-development-orchestrator:agent-task:issue:{issue_number} -->"


def agent_task_endpoint(repo: str) -> str:
    return f"https://api.github.com/agents/repos/{repo}/tasks"


def build_agent_task_payload(base_branch: str, instructions: str) -> dict[str, Any]:
    return {
        "prompt": instructions,
        "create_pull_request": False,
        "base_ref": base_branch,
    }


def build_agent_task_instructions(issue: dict[str, Any], base_branch: str) -> str:
    number = int(issue["number"])
    title = str(issue.get("title") or "").strip()
    body = str(issue.get("body") or "").strip()
    marker = agent_task_marker(number)
    return (
        f"{marker}\n"
        f"ReqSys issue #{number}: {title}\n\n"
        f"{body}\n\n"
        "Siga AGENTS.md e as regras operacionais canônicas do ReqSys. "
        "Trabalhe em branch isolada a partir da base informada, preserve o escopo da issue e faça a menor implementação real. "
        "Inclua testes automatizados e validação ponta a ponta aplicável, com controles contra falso positivo e idempotência quando aplicável. "
        "Não abra Pull Request, não faça merge, não faça deploy de produção, não altere segredos, permissões administrativas ou branch protection. "
        "A Pull Request somente poderá ser aberta pelo fluxo governado após READY_FOR_PR=passed. "
        f"Base esperada: {base_branch}."
    )


def start_agent_task(client: core.GitHubClient, base_branch: str, instructions: str) -> dict[str, Any]:
    if not client.copilot_token:
        raise core.GitHubApiError("COPILOT_AGENT_TOKEN ausente para Agent Tasks")

    payload = build_agent_task_payload(base_branch, instructions)
    request = Request(
        agent_task_endpoint(client.repo),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {client.copilot_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": AGENT_TASK_API_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - GitHub API only.
            content = response.read().decode("utf-8")
            task = json.loads(content) if content else {}
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise core.GitHubApiError(
            f"GitHub Agent Tasks error {exc.code}: {error_body[:500]}"
        ) from exc
    except URLError as exc:
        raise core.GitHubApiError(f"GitHub Agent Tasks connection error: {exc}") from exc

    if not isinstance(task, dict) or not task.get("id"):
        raise core.GitHubApiError("GitHub Agent Tasks retornou resposta sem task id")
    return task


def record_agent_task_dispatch(
    client: core.GitHubClient,
    issue_number: int,
    task: dict[str, Any],
) -> None:
    marker = agent_task_marker(issue_number)
    task_id = str(task.get("id") or "")
    task_url = str(task.get("html_url") or task.get("url") or "")
    body = (
        f"{marker}\n"
        "Pending Development Orchestrator: Agent Task branch-first criada com `create_pull_request=false`.\n\n"
        f"- task_id: `{task_id}`\n"
        f"- task_url: {task_url or 'indisponível'}\n"
        "- próximo gate obrigatório: `READY_FOR_PR=passed` antes da abertura de Pull Request."
    )
    client.request("POST", f"issues/{issue_number}/comments", payload={"body": body})


def _existing_agent_task_marker(client: core.GitHubClient, issue_number: int) -> bool:
    marker = agent_task_marker(issue_number)
    comments = client.list_comments(issue_number, use_copilot_token=False)
    return any(marker in str(comment.get("body") or "") for comment in comments)


def process_issue_branch_first(
    client: core.GitHubClient,
    issue: dict[str, Any],
    status_report: dict[str, Any],
    *,
    execute: bool,
    base_branch: str,
    dispatched_routes: set[str],
    fallback: Callable[..., core.Decision],
) -> core.Decision:
    """Troca somente a rota de desenvolvimento de issue; demais rotas ficam canônicas."""
    planned = fallback(
        client,
        issue,
        status_report,
        execute=False,
        base_branch=base_branch,
        dispatched_routes=dispatched_routes,
    )

    if planned.route != "copilot_issue_agent" or planned.status != "planned":
        return fallback(
            client,
            issue,
            status_report,
            execute=execute,
            base_branch=base_branch,
            dispatched_routes=dispatched_routes,
        )

    number = int(issue["number"])
    title = str(issue.get("title") or "")
    if _existing_agent_task_marker(client, number):
        return core.Decision(
            "issue",
            number,
            title,
            AGENT_TASK_ROUTE,
            "already_dispatched",
            "agent_task_marker_already_present",
            planned.risk,
            planned.increment_type,
            planned.gate_reason,
            url=planned.url,
        )

    if not execute:
        return core.Decision(
            "issue",
            number,
            title,
            AGENT_TASK_ROUTE,
            "planned",
            "eligible_issue_backed_development_branch_first",
            planned.risk,
            planned.increment_type,
            planned.gate_reason,
            url=planned.url,
        )

    if not client.copilot_token:
        return core.Decision(
            "issue",
            number,
            title,
            AGENT_TASK_ROUTE,
            "blocked",
            "missing_copilot_agent_task_token",
            planned.risk,
            planned.increment_type,
            planned.gate_reason,
            url=planned.url,
        )

    instructions = build_agent_task_instructions(issue, base_branch)
    task = start_agent_task(client, base_branch, instructions)
    record_agent_task_dispatch(client, number, task)
    return core.Decision(
        "issue",
        number,
        title,
        AGENT_TASK_ROUTE,
        "dispatched",
        "eligible_issue_backed_development_branch_first",
        planned.risk,
        planned.increment_type,
        planned.gate_reason,
        True,
        url=planned.url,
    )


def install_agent_task_route() -> None:
    """Instala a rota branch-first uma vez por processo do entrypoint."""
    if getattr(core, _INSTALL_MARKER, False):
        return

    original_process_issue = core.process_issue
    original_build_report = core.build_report

    def process_issue(
        client: core.GitHubClient,
        issue: dict[str, Any],
        status_report: dict[str, Any],
        *,
        execute: bool,
        base_branch: str,
        dispatched_routes: set[str],
    ) -> core.Decision:
        return process_issue_branch_first(
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
        if AGENT_TASK_GUARDRAIL not in guardrails:
            guardrails.append(AGENT_TASK_GUARDRAIL)
        return report

    core.process_issue = process_issue
    core.build_report = build_report
    setattr(core, _INSTALL_MARKER, True)
