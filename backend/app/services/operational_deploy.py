from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests

from app.core.resilience import CircuitBreaker, CircuitBreakerOpenError, call_with_retry

_REPOSITORY = 'ericson-j-santos/reqsys-v2-enterprise-real'
_WORKFLOW = 'fly-governed-command-center.yml'
_API_BASE = 'https://api.github.com'
_APPS_DEV = {
    'backend': 'reqsys-api-dev',
    'frontend': 'reqsys-app-dev',
}
_circuit = CircuitBreaker(name='operational_deploy_github', failure_threshold=3, cooldown_seconds=60)


@dataclass(frozen=True)
class OperacaoDeploy:
    operacao_id: str
    correlation_id: str
    aplicacao: str
    ambiente: str
    app_name: str
    status: str
    production_touched: bool
    solicitado_em: str
    idempotency_key: str


def _token() -> str:
    return (os.getenv('GITHUB_TOKEN') or os.getenv('REQSYS_GITHUB_TOKEN') or '').strip()


def _idempotency_key(aplicacao: str, sha: str) -> str:
    material = f'deploy|development|{aplicacao}|{sha}'.encode('utf-8')
    return hashlib.sha256(material).hexdigest()


def preparar_deploy_dev(aplicacao: str, sha: str = 'main') -> OperacaoDeploy:
    app = _APPS_DEV.get(aplicacao)
    if not app:
        raise ValueError('Aplicação não permitida. Use backend ou frontend.')
    agora = datetime.now(UTC).isoformat()
    chave = _idempotency_key(aplicacao, sha)
    correlation_id = f'REQSYS-DEPLOY-{chave[:16]}'
    return OperacaoDeploy(
        operacao_id=chave[:24],
        correlation_id=correlation_id,
        aplicacao=aplicacao,
        ambiente='development',
        app_name=app,
        status='VALIDADO',
        production_touched=False,
        solicitado_em=agora,
        idempotency_key=chave,
    )


def executar_deploy_dev(aplicacao: str, *, ref: str = 'main') -> dict[str, Any]:
    operacao = preparar_deploy_dev(aplicacao, ref)
    token = _token()
    if not token:
        raise RuntimeError('Credencial GitHub para execução governada não configurada')

    url = f'{_API_BASE}/repos/{_REPOSITORY}/actions/workflows/{_WORKFLOW}/dispatches'
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28',
        'X-ReqSys-Correlation-Id': operacao.correlation_id,
    }
    payload = {
        'ref': ref,
        'inputs': {
            'app_name': operacao.app_name,
            'environment': 'development',
            'command': 'deploy',
            'scale_count': '1',
            'confirmacao': '',
        },
    }

    def _dispatch() -> requests.Response:
        resposta = requests.post(url, headers=headers, json=payload, timeout=20)
        if resposta.status_code not in {204}:
            resposta.raise_for_status()
        return resposta

    try:
        resposta = call_with_retry(
            _dispatch,
            max_retries=2,
            backoff_seconds=0.5,
            retry_on=(requests.ConnectionError, requests.Timeout),
            circuit=_circuit,
        )
    except CircuitBreakerOpenError as exc:
        raise RuntimeError('Circuito GitHub Actions temporariamente aberto') from exc

    return {
        **operacao.__dict__,
        'status': 'EM_EXECUCAO',
        'http_status_dispatch': resposta.status_code,
        'workflow': _WORKFLOW,
        'repository': _REPOSITORY,
        'ref': ref,
        'approval_mode': 'single_confirmation_dev',
    }
