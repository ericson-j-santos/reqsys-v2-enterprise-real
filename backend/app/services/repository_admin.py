from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services import github_client

ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = ROOT_DIR / 'config' / 'repository-admin-registry.json'
REPOSITORY_RE = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')

FAILURE_CONCLUSIONS = {
    'action_required',
    'cancelled',
    'failure',
    'stale',
    'startup_failure',
    'timed_out',
}
INCONCLUSIVE_CONCLUSIONS = {'neutral', 'skipped'}


class RepositoryAdminError(RuntimeError):
    pass


def _validate_repository(item: dict[str, Any]) -> dict[str, Any]:
    name = str(item.get('name') or '').strip()
    provider = str(item.get('provider') or '').strip().lower()
    default_branch = str(item.get('default_branch') or '').strip()

    if not REPOSITORY_RE.fullmatch(name):
        raise RepositoryAdminError(f'Repositorio invalido no registry: {name!r}.')
    if provider != 'github':
        raise RepositoryAdminError(f'Provider nao suportado para {name}: {provider!r}.')
    if not default_branch or '/' in default_branch or default_branch.startswith('.'):
        raise RepositoryAdminError(f'Default branch invalida para {name}.')

    return {
        'name': name,
        'provider': provider,
        'default_branch': default_branch,
        'mode': str(item.get('mode') or 'read_only'),
        'tracking_issue': item.get('tracking_issue'),
        'gates': list(item.get('gates') or []),
        'capabilities': dict(item.get('capabilities') or {}),
    }


def load_registry(path: Path | None = None) -> dict[str, Any]:
    source = path or DEFAULT_REGISTRY_PATH
    try:
        payload = json.loads(source.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise RepositoryAdminError('Registry de repositorios invalido ou indisponivel.') from exc

    repositories = payload.get('repositories')
    if not isinstance(repositories, list) or not repositories:
        raise RepositoryAdminError('Registry deve conter ao menos um repositorio.')

    normalized = [_validate_repository(dict(item)) for item in repositories]
    names = [item['name'] for item in normalized]
    if len(names) != len(set(names)):
        raise RepositoryAdminError('Registry contem repositorios duplicados.')

    return {
        'schema_version': str(payload.get('schema_version') or '1.0.0'),
        'repositories': normalized,
    }


def list_repositories(path: Path | None = None) -> list[dict[str, Any]]:
    return load_registry(path)['repositories']


def get_repository(repository: str, path: Path | None = None) -> dict[str, Any]:
    for item in list_repositories(path):
        if item['name'] == repository:
            return item
    raise RepositoryAdminError(f'Repositorio nao administrado: {repository}.')


def build_snapshot(repository: str) -> dict[str, Any]:
    definition = get_repository(repository)
    branch = definition['default_branch']
    sha = github_client.get_branch_sha(repository, branch)
    if not sha:
        raise RepositoryAdminError(
            f'Nao foi possivel resolver o SHA de {repository}@{branch}.'
        )
    return {
        'repository': repository,
        'provider': definition['provider'],
        'default_branch': branch,
        'sha': sha,
        'mode': definition['mode'],
        'gates': definition['gates'],
        'captured_at': datetime.now(UTC).isoformat(),
    }


def _latest_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for check in checks:
        name = str(check.get('name') or 'check-sem-nome')
        current = latest.get(name)
        candidate_key = (
            str(check.get('completed_at') or check.get('started_at') or ''),
            int(check.get('id') or 0),
        )
        current_key = (
            str((current or {}).get('completed_at') or (current or {}).get('started_at') or ''),
            int((current or {}).get('id') or 0),
        )
        if current is None or candidate_key >= current_key:
            latest[name] = check
    return [latest[name] for name in sorted(latest)]


def summarize_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        'total': 0,
        'success': [],
        'failed': [],
        'pending': [],
        'inconclusive': [],
    }
    for check in _latest_checks(checks):
        name = str(check.get('name') or 'check-sem-nome')
        status = str(check.get('status') or 'unknown')
        conclusion = str(check.get('conclusion') or '').lower()
        summary['total'] += 1
        if status != 'completed':
            summary['pending'].append(name)
        elif conclusion == 'success':
            summary['success'].append(name)
        elif conclusion in FAILURE_CONCLUSIONS:
            summary['failed'].append(name)
        else:
            summary['inconclusive'].append(name)
    return summary


def decide_pull_request(repository: str, pull_request: int) -> dict[str, Any]:
    definition = get_repository(repository)
    pr = github_client.get_pull_request(repository, pull_request)
    head_sha = str(((pr.get('head') or {}).get('sha') or '')).lower()
    checks = github_client.list_check_runs(repository, head_sha) if head_sha else []
    check_summary = summarize_checks(checks)
    base_branch = str((pr.get('base') or {}).get('ref') or '')

    if pr.get('state') != 'open':
        decision = 'blocked_pr_not_open'
    elif pr.get('draft'):
        decision = 'wait_draft'
    elif base_branch != definition['default_branch']:
        decision = 'blocked_unexpected_base'
    elif pr.get('mergeable') is False:
        decision = 'blocked_conflict'
    elif check_summary['failed']:
        decision = 'fix_ci'
    elif check_summary['pending']:
        decision = 'wait_ci'
    elif not check_summary['total']:
        decision = 'no_ci_evidence'
    elif check_summary['inconclusive']:
        decision = 'investigate_ci'
    elif pr.get('mergeable') is not True:
        decision = 'wait_mergeability'
    else:
        decision = 'ready_for_full_gates'

    return {
        'repository': repository,
        'pull_request': pull_request,
        'head_sha': head_sha or None,
        'base_branch': base_branch or None,
        'state': pr.get('state'),
        'draft': bool(pr.get('draft')),
        'mergeable': pr.get('mergeable'),
        'decision': decision,
        'checks': check_summary,
        'automatic_action_allowed': False,
        'evidence_scope': {
            'repository': repository,
            'pull_request': pull_request,
            'head_sha': head_sha or None,
        },
    }
