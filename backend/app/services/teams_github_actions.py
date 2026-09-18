from __future__ import annotations

import logging
import re
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.core.secrets import get_secret

logger = logging.getLogger('reqsys.teams_github_actions')

TeamsGithubActionsMode = Literal['essential', 'all']

_ALLOWED_MODES = {'essential', 'all'}
_DEFAULT_WORKFLOW = 'actions-dispatcher.yml'
_REF_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$')
_REPO_PATTERN = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


class TeamsGithubActionsError(RuntimeError):
    """Erro controlado da ponte Teams -> GitHub Actions."""

    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def _bool_config(name: str, default: str = 'false') -> bool:
    return (get_secret(name, default) or default).strip().lower() in {'1', 'true', 'yes', 'on'}


def _repo_configurado() -> str:
    return (get_secret('TEAMS_GITHUB_ACTIONS_REPO', '') or '').strip()


def _workflow_configurado() -> str:
    return (get_secret('TEAMS_GITHUB_ACTIONS_WORKFLOW', _DEFAULT_WORKFLOW) or _DEFAULT_WORKFLOW).strip()


def _dispatch_ref_configurado() -> str:
    return (get_secret('TEAMS_GITHUB_ACTIONS_DISPATCH_REF', 'main') or 'main').strip()


def _validar_ref(ref: str) -> str:
    value = ref.strip()
    if (
        not _REF_PATTERN.fullmatch(value)
        or '..' in value
        or '@{' in value
        or '//' in value
        or value.endswith('/')
        or value.endswith('.lock')
    ):
        raise TeamsGithubActionsError('Ref Git invalida para disparo governado.')
    return value


def _validar_repo(repo: str) -> str:
    if not _REPO_PATTERN.fullmatch(repo):
        raise TeamsGithubActionsError('TEAMS_GITHUB_ACTIONS_REPO ausente ou invalido.', status_code=503)
    return repo


def status_teams_github_actions() -> dict[str, Any]:
    repo = _repo_configurado()
    workflow = _workflow_configurado()
    enabled = _bool_config('TEAMS_GITHUB_ACTIONS_ENABLED', 'false')
    return {
        'enabled': enabled,
        'configured': bool(enabled and settings.github_pat and repo and workflow),
        'repository': repo or None,
        'workflow': workflow,
        'dispatch_ref': _dispatch_ref_configurado(),
        'allowed_modes': sorted(_ALLOWED_MODES),
        'token_configured': bool(settings.github_pat),
    }


async def despachar_verificacoes_github(
    *,
    mode: TeamsGithubActionsMode,
    target_ref: str,
    correlation_id: str,
    actor: str,
) -> dict[str, Any]:
    """Dispara somente o workflow central permitido para a ref solicitada.

    O payload recebido do Teams nunca controla repositório, workflow, URL ou
    credencial. Esses valores são definidos no servidor; o usuário escolhe
    apenas um modo previamente permitido e uma ref Git validada.
    """
    if not _bool_config('TEAMS_GITHUB_ACTIONS_ENABLED', 'false'):
        raise TeamsGithubActionsError('Acoes GitHub via Teams estao desabilitadas.', status_code=503)
    if not settings.github_pat:
        raise TeamsGithubActionsError('GITHUB_PAT nao configurado no ReqSys.', status_code=503)
    if mode not in _ALLOWED_MODES:
        raise TeamsGithubActionsError('Modo de verificacao nao permitido.')

    repo = _validar_repo(_repo_configurado())
    workflow = _workflow_configurado()
    if not workflow or '/' in workflow or '\\' in workflow or not workflow.endswith(('.yml', '.yaml')):
        raise TeamsGithubActionsError('TEAMS_GITHUB_ACTIONS_WORKFLOW invalido.', status_code=503)

    target = _validar_ref(target_ref)
    dispatch_ref = _validar_ref(_dispatch_ref_configurado())
    url = f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches'
    request_body = {
        'ref': dispatch_ref,
        'inputs': {
            'ref': target,
            'mode': mode,
        },
    }
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {settings.github_pat}',
        'X-GitHub-Api-Version': '2022-11-28',
        'X-ReqSys-Correlation-ID': correlation_id,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=request_body, headers=headers)
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning(
            'teams_github_actions_transport_error correlation_id=%s actor=%s mode=%s ref=%s error=%s',
            correlation_id,
            actor,
            mode,
            target,
            type(exc).__name__,
        )
        raise TeamsGithubActionsError('GitHub indisponivel para o disparo.', status_code=502) from exc

    if response.status_code not in {200, 204}:
        logger.warning(
            'teams_github_actions_dispatch_failed correlation_id=%s actor=%s mode=%s ref=%s status=%s',
            correlation_id,
            actor,
            mode,
            target,
            response.status_code,
        )
        if response.status_code in {401, 403}:
            message = 'Credencial GitHub sem permissao para executar Actions.'
        elif response.status_code == 404:
            message = 'Repositorio ou workflow governado nao encontrado no GitHub.'
        elif response.status_code == 422:
            message = 'GitHub rejeitou a ref ou os parametros do workflow.'
        else:
            message = 'GitHub recusou o disparo do workflow.'
        raise TeamsGithubActionsError(message, status_code=502)

    response_data: dict[str, Any] = {}
    if response.content:
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                response_data = parsed
        except ValueError:
            response_data = {}

    run_url = response_data.get('html_url') if isinstance(response_data.get('html_url'), str) else None
    workflow_url = f'https://github.com/{repo}/actions/workflows/{workflow}'
    logger.info(
        'teams_github_actions_dispatched correlation_id=%s actor=%s mode=%s ref=%s',
        correlation_id,
        actor,
        mode,
        target,
    )
    return {
        'dispatched': True,
        'status': 'solicitado',
        'mode': mode,
        'ref': target,
        'correlation_id': correlation_id,
        'workflow_url': workflow_url,
        'run_url': run_url,
        'run_id': response_data.get('workflow_run_id'),
    }
