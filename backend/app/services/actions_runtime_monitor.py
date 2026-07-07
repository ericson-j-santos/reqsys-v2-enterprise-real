from __future__ import annotations

import os
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from app.core.resilience import CircuitBreaker, CircuitBreakerOpenError, call_with_retry

ACTIONS_MONITOR_MAX_RETRIES = 3
ACTIONS_MONITOR_RETRY_BACKOFF_SECONDS = 0.5
ACTIONS_MONITOR_CIRCUIT_FAILURE_THRESHOLD = 3
ACTIONS_MONITOR_CIRCUIT_COOLDOWN_SECONDS = 60

_circuits: dict[str, CircuitBreaker] = {}


def _circuit_for(url: str) -> CircuitBreaker:
    host = urlparse(url).netloc or 'default'
    if host not in _circuits:
        _circuits[host] = CircuitBreaker(
            name=f'actions_runtime_monitor_{host}',
            failure_threshold=ACTIONS_MONITOR_CIRCUIT_FAILURE_THRESHOLD,
            cooldown_seconds=ACTIONS_MONITOR_CIRCUIT_COOLDOWN_SECONDS,
        )
    return _circuits[host]


def reset_circuit_breakers() -> None:
    """Reseta todos os circuit breakers deste monitor (uso em testes)."""
    for circuit in _circuits.values():
        circuit.reset()


@dataclass(frozen=True)
class WorkflowRunSnapshot:
    run_id: int
    workflow: str
    status: str
    conclusion: str | None
    branch: str | None
    event: str | None
    commit_sha: str | None
    html_url: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def health(self) -> str:
        if self.status != 'completed':
            return 'running'
        if self.conclusion == 'success':
            return 'healthy'
        if self.conclusion in {'failure', 'cancelled', 'timed_out', 'action_required'}:
            return 'unhealthy'
        return 'unknown'


def normalizar_run(raw: dict[str, Any]) -> WorkflowRunSnapshot:
    return WorkflowRunSnapshot(
        run_id=int(raw.get('id') or 0),
        workflow=str(raw.get('name') or raw.get('workflow_name') or 'workflow-desconhecido'),
        status=str(raw.get('status') or 'unknown'),
        conclusion=raw.get('conclusion'),
        branch=raw.get('head_branch'),
        event=raw.get('event'),
        commit_sha=raw.get('head_sha'),
        html_url=raw.get('html_url'),
        created_at=raw.get('created_at'),
        updated_at=raw.get('updated_at'),
    )


def classificar_runs(runs: list[WorkflowRunSnapshot]) -> dict[str, Any]:
    por_health = Counter(run.health for run in runs)
    por_workflow = Counter(run.workflow for run in runs)
    falhas = [run for run in runs if run.health == 'unhealthy']
    em_execucao = [run for run in runs if run.health == 'running']

    total = len(runs)
    saudaveis = por_health.get('healthy', 0)
    score = round((saudaveis / total) * 100, 2) if total else 100.0

    return {
        'total_runs': total,
        'score_saude': score,
        'por_status_operacional': dict(por_health),
        'por_workflow': dict(por_workflow),
        'falhas': [run.__dict__ | {'health': run.health} for run in falhas[:10]],
        'em_execucao': [run.__dict__ | {'health': run.health} for run in em_execucao[:10]],
        'decisao': decidir_estado(score, falhas, em_execucao),
        'atualizado_em': datetime.now(timezone.utc).isoformat(),
    }


def decidir_estado(score: float, falhas: list[WorkflowRunSnapshot], em_execucao: list[WorkflowRunSnapshot]) -> str:
    if falhas:
        return 'corrigir_falhas_de_actions_antes_de_novo_merge'
    if em_execucao:
        return 'aguardar_finalizacao_dos_workflows'
    if score >= 95:
        return 'operacao_estavel'
    return 'investigar_instabilidade_operacional'


class GitHubActionsClient:
    def __init__(self, token: str | None = None, api_base: str = 'https://api.github.com') -> None:
        self.token = token or os.getenv('GITHUB_TOKEN') or os.getenv('REQSYS_GITHUB_TOKEN')
        self.api_base = api_base.rstrip('/')

    def listar_runs(
        self,
        repo: str,
        branch: str = 'main',
        per_page: int = 20,
        *,
        sleep=time.sleep,
        max_retries: int = ACTIONS_MONITOR_MAX_RETRIES,
    ) -> list[WorkflowRunSnapshot]:
        if not self.token:
            raise RuntimeError('GITHUB_TOKEN ou REQSYS_GITHUB_TOKEN ausente')

        url = f'{self.api_base}/repos/{repo}/actions/runs'
        headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {self.token}',
            'X-GitHub-Api-Version': '2022-11-28',
        }
        params = {'branch': branch, 'per_page': min(max(per_page, 1), 50)}

        def _do() -> Any:
            resposta = requests.get(url, headers=headers, params=params, timeout=30)
            resposta.raise_for_status()
            return resposta.json()

        try:
            dados = call_with_retry(
                _do,
                max_retries=max_retries,
                backoff_seconds=ACTIONS_MONITOR_RETRY_BACKOFF_SECONDS,
                retry_on=(requests.ConnectionError, requests.Timeout),
                sleep=sleep,
                circuit=_circuit_for(url),
            )
        except CircuitBreakerOpenError as exc:
            raise requests.ConnectionError(str(exc)) from exc
        return [normalizar_run(item) for item in dados.get('workflow_runs', [])]


def _pareto_falhas(runs: list[WorkflowRunSnapshot]) -> dict[str, Any]:
    """Ranking Pareto simplificado por workflow com falhas."""
    buckets: dict[str, dict[str, Any]] = {}
    for run in runs:
        if run.health != 'unhealthy':
            continue
        bucket = buckets.setdefault(
            run.workflow,
            {'workflow': run.workflow, 'occurrences': 0, 'impact_score': 0, 'severidade': 'high'},
        )
        bucket['occurrences'] += 1
        bucket['impact_score'] += 80

    items = sorted(buckets.values(), key=lambda item: item['impact_score'], reverse=True)
    total_impact = sum(item['impact_score'] for item in items) or 1
    cumulative = 0.0
    for item in items:
        cumulative += (item['impact_score'] / total_impact) * 100
        item['cumulative_percent'] = round(cumulative, 2)
        item['pareto_tier'] = 'A' if cumulative <= 80 else ('B' if cumulative <= 95 else 'C')

    return {
        'total_causes': len(items),
        'top_causes': items[:10],
        'pareto_threshold_80': [item for item in items if item['cumulative_percent'] <= 80 or item == items[0]],
    }


def montar_snapshot_operacional(runs_raw: list[dict[str, Any]]) -> dict[str, Any]:
    runs = [normalizar_run(item) for item in runs_raw]
    resumo = classificar_runs(runs)
    resumo['pareto_falhas'] = _pareto_falhas(runs)
    return resumo
