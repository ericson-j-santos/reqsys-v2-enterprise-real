from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


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

    def listar_runs(self, repo: str, branch: str = 'main', per_page: int = 20) -> list[WorkflowRunSnapshot]:
        if not self.token:
            raise RuntimeError('GITHUB_TOKEN ou REQSYS_GITHUB_TOKEN ausente')

        url = f'{self.api_base}/repos/{repo}/actions/runs'
        headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {self.token}',
            'X-GitHub-Api-Version': '2022-11-28',
        }
        params = {'branch': branch, 'per_page': min(max(per_page, 1), 50)}
        resposta = requests.get(url, headers=headers, params=params, timeout=30)
        resposta.raise_for_status()
        dados = resposta.json()
        return [normalizar_run(item) for item in dados.get('workflow_runs', [])]


def montar_snapshot_operacional(runs_raw: list[dict[str, Any]]) -> dict[str, Any]:
    runs = [normalizar_run(item) for item in runs_raw]
    return classificar_runs(runs)
