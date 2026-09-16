#!/usr/bin/env python3
"""Entrypoint fail-closed para o Pending Development Orchestrator.

Aplica uma política de confiança à descoberta automática de issues antes de
delegar ao orquestrador canônico. O objetivo é impedir que título ou marcador
controlado por autor externo acorde uma automação com permissões de escrita.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import pending_development_orchestrator as core  # noqa: E402
from scripts.pending_development_agent_tasks import install_agent_task_route  # noqa: E402
from scripts.pending_development_local_codex import install_local_codex_fallback  # noqa: E402

TRUSTED_AUTOMATION_ACTORS = {"github-actions[bot]"}
TRUST_GUARDRAIL = "trusted_issue_source_or_privileged_auto_label"


def _author_login(issue: dict[str, Any]) -> str:
    user = issue.get("user") or {}
    return str(user.get("login") or "").strip().lower()


def _has_marker_or_title(issue: dict[str, Any]) -> bool:
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    return core.AUTO_MARKER in body or title.upper().startswith("[AUTO-NEXT]")


def issue_source_is_trusted(issue: dict[str, Any], repo_owner: str) -> bool:
    """Aceita label privilegiada ou conteúdo criado por origem confiável."""
    if issue.get("pull_request"):
        return False
    labels = core._label_names(issue)
    if core.AUTO_LABEL in labels:
        return True
    author = _author_login(issue)
    trusted_authors = TRUSTED_AUTOMATION_ACTORS | {repo_owner.strip().lower()}
    return author in trusted_authors and _has_marker_or_title(issue)


def trusted_issue_candidate(
    issue: dict[str, Any],
    *,
    repo_owner: str,
    event_name: str,
    explicitly_selected: bool = False,
) -> bool:
    """Replica o gate de candidato sem confiar em texto de terceiros."""
    if issue.get("pull_request"):
        return False

    # workflow_dispatch com número explícito é uma seleção privilegiada do operador.
    if explicitly_selected and event_name != "issues":
        return True

    trusted = issue_source_is_trusted(issue, repo_owner)
    if explicitly_selected:
        return trusted
    if core.deferred_scope(issue):
        return False
    return trusted


def install_trusted_policy(repo_owner: str, event_name: str) -> None:
    """Instala o filtro no módulo canônico somente para esta execução."""
    def candidate(issue: dict[str, Any], *, explicitly_selected: bool = False) -> bool:
        return trusted_issue_candidate(
            issue,
            repo_owner=repo_owner,
            event_name=event_name,
            explicitly_selected=explicitly_selected,
        )

    original_build_report: Callable[..., dict[str, Any]] = core.build_report

    def build_report(*args: Any, **kwargs: Any) -> dict[str, Any]:
        report = original_build_report(*args, **kwargs)
        guardrails = report.setdefault("guardrails", [])
        if TRUST_GUARDRAIL not in guardrails:
            guardrails.append(TRUST_GUARDRAIL)
        return report

    core.is_issue_candidate = candidate
    core.build_report = build_report


def _argument_value(args: list[str], name: str) -> str:
    try:
        index = args.index(name)
    except ValueError:
        return ""
    return args[index + 1] if index + 1 < len(args) else ""


def main(argv: list[str] | None = None) -> int:
    raw_args = list(argv if argv is not None else os.sys.argv[1:])
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    known, passthrough = parser.parse_known_args(raw_args)

    repo = _argument_value(passthrough, "--repo") or os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        return core.main(passthrough)

    repo_owner = repo.split("/", 1)[0]
    install_trusted_policy(repo_owner, str(known.event_name or ""))
    install_agent_task_route()
    install_local_codex_fallback()
    return core.main(passthrough)


if __name__ == "__main__":
    raise SystemExit(main())
