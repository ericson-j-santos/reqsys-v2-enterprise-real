"""
hub_lowcode.py — Agrega dados de baixo código para o Hub: SharePoint, Power Automate, GitHub.

Todos os métodos degradam graciosamente quando as credenciais não estão configuradas,
retornando listas vazias com flag `configurado=False` em vez de lançar exceção.
"""
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger('reqsys.hub_lowcode')

_GRAPH_TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
_GRAPH_BASE = 'https://graph.microsoft.com/v1.0'
_PA_TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
_PA_BASE = 'https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple'
_GH_BASE = 'https://api.github.com'


def _tem_credenciais_graph() -> bool:
    return bool(settings.azure_tenant_id and settings.azure_client_id and settings.azure_client_secret)


async def _token_grafico() -> str:
    """Obtém access token para Graph API via client_credentials."""
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(
            _GRAPH_TOKEN_URL.format(tenant=settings.azure_tenant_id),
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.azure_client_id,
                'client_secret': settings.azure_client_secret,
                'scope': 'https://graph.microsoft.com/.default',
            },
        )
        resp.raise_for_status()
        return resp.json()['access_token']


async def _token_power_automate() -> str:
    """Obtém access token para o Power Automate Management API."""
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(
            _PA_TOKEN_URL.format(tenant=settings.azure_tenant_id),
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.azure_client_id,
                'client_secret': settings.azure_client_secret,
                'scope': 'https://service.flow.microsoft.com/.default',
            },
        )
        resp.raise_for_status()
        return resp.json()['access_token']


async def listar_pacotes_ia(limit: int = 20) -> dict[str, Any]:
    """
    Lê a lista SharePoint IA_Catalogo_Projetos via Graph API.
    Retorna: { configurado, itens, erro }
    """
    if not _tem_credenciais_graph() or not settings.sharepoint_site_id:
        return {'configurado': False, 'itens': [], 'erro': 'Credenciais Graph ou SHAREPOINT_SITE_ID não configurados'}

    try:
        token = await _token_grafico()
        url = (
            f'{_GRAPH_BASE}/sites/{settings.sharepoint_site_id}'
            f'/lists/{settings.sharepoint_list_ia}/items'
            f'?$expand=fields'
            f'&$orderby=fields/ProcessadoEmUtc desc'
            f'&$top={limit}'
        )
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(url, headers={'Authorization': f'Bearer {token}'})
            resp.raise_for_status()
            raw = resp.json().get('value', [])

        itens = []
        for item in raw:
            f = item.get('fields', {})
            itens.append({
                'id': item.get('id'),
                'projeto': f.get('Projeto', ''),
                'branch': f.get('Branch', ''),
                'commit': (f.get('CommitHash') or '')[:12],
                'tech_stack': f.get('TechStack', ''),
                'total_arquivos': f.get('TotalArquivos', 0),
                'tamanho_mb': f.get('TamanhoPacoteMb', 0),
                'status': f.get('Status', ''),
                'chave': f.get('ChaveIdempotencia', ''),
                'gerado_em': f.get('DataGeracaoUtc', ''),
                'processado_em': f.get('ProcessadoEmUtc', ''),
            })
        return {'configurado': True, 'itens': itens, 'erro': None}

    except Exception as exc:
        logger.warning('hub_lowcode: erro ao ler pacotes SP: %s', exc)
        return {'configurado': True, 'itens': [], 'erro': str(exc)}


async def listar_flows_pa() -> dict[str, Any]:
    """
    Lista flows do Power Automate e as últimas execuções do flow principal.
    Retorna: { configurado, flows, execucoes, erro }
    """
    if not _tem_credenciais_graph() or not settings.powerautomate_env_id:
        return {'configurado': False, 'flows': [], 'execucoes': [], 'erro': 'POWERAUTOMATE_ENV_ID não configurado'}

    try:
        token = await _token_power_automate()
        headers = {'Authorization': f'Bearer {token}'}
        env = settings.powerautomate_env_id

        async with httpx.AsyncClient(timeout=15) as c:
            # Lista flows do ambiente
            r_flows = await c.get(
                f'{_PA_BASE}/environments/{env}/flows?api-version=2016-11-01',
                headers=headers,
            )
            r_flows.raise_for_status()
            flows_raw = r_flows.json().get('value', [])

        flows = [
            {
                'id': f.get('name'),
                'nome': f.get('properties', {}).get('displayName', ''),
                'estado': f.get('properties', {}).get('state', ''),
                'criado_em': f.get('properties', {}).get('createdTime', ''),
                'modificado_em': f.get('properties', {}).get('lastModifiedTime', ''),
            }
            for f in flows_raw
        ]

        # Execuções do flow principal
        execucoes = []
        flow_id = settings.powerautomate_flow_id
        if flow_id:
            try:
                async with httpx.AsyncClient(timeout=15) as c:
                    r_runs = await c.get(
                        f'{_PA_BASE}/environments/{env}/flows/{flow_id}/runs?api-version=2016-11-01&$top=10',
                        headers=headers,
                    )
                    r_runs.raise_for_status()
                    runs_raw = r_runs.json().get('value', [])

                execucoes = [
                    {
                        'id': r.get('name'),
                        'inicio': r.get('properties', {}).get('startTime', ''),
                        'fim': r.get('properties', {}).get('endTime', ''),
                        'status': r.get('properties', {}).get('status', ''),
                        'codigo': r.get('properties', {}).get('code', ''),
                    }
                    for r in runs_raw
                ]
            except Exception as exc_runs:
                logger.warning('hub_lowcode: erro ao ler execucoes flow: %s', exc_runs)

        return {'configurado': True, 'flows': flows, 'execucoes': execucoes, 'erro': None}

    except Exception as exc:
        logger.warning('hub_lowcode: erro ao ler flows PA: %s', exc)
        return {'configurado': True, 'flows': [], 'execucoes': [], 'erro': str(exc)}


async def listar_runs_github(limit: int = 10) -> dict[str, Any]:
    """
    Lista as últimas execuções do GitHub Actions no repo ALM.
    Retorna: { configurado, runs, erro }
    """
    repo = settings.github_alm_repo
    if not repo:
        return {'configurado': False, 'runs': [], 'erro': 'GITHUB_ALM_REPO não configurado'}

    headers: dict[str, str] = {'Accept': 'application/vnd.github+json'}
    if settings.github_pat:
        headers['Authorization'] = f'token {settings.github_pat}'

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f'{_GH_BASE}/repos/{repo}/actions/runs?per_page={limit}',
                headers=headers,
            )
            resp.raise_for_status()
            runs_raw = resp.json().get('workflow_runs', [])

        runs = [
            {
                'id': r.get('id'),
                'nome': r.get('name', ''),
                'workflow': r.get('path', '').split('/')[-1],
                'branch': r.get('head_branch', ''),
                'commit': (r.get('head_sha') or '')[:8],
                'status': r.get('status', ''),
                'conclusao': r.get('conclusion', ''),
                'criado_em': r.get('created_at', ''),
                'url': r.get('html_url', ''),
            }
            for r in runs_raw
        ]
        return {'configurado': True, 'runs': runs, 'erro': None}

    except Exception as exc:
        logger.warning('hub_lowcode: erro ao ler GitHub Actions: %s', exc)
        return {'configurado': True, 'runs': [], 'erro': str(exc)}


async def status_consolidado() -> dict[str, Any]:
    """Resumo rápido para o card do Dashboard."""
    pacotes_r = await listar_pacotes_ia(limit=1)
    github_r = await listar_runs_github(limit=1)

    ultimo_pacote = pacotes_r['itens'][0] if pacotes_r['itens'] else None
    ultimo_run = github_r['runs'][0] if github_r['runs'] else None

    return {
        'pacotes_configurado': pacotes_r['configurado'],
        'ultimo_pacote': ultimo_pacote,
        'github_configurado': github_r['configurado'],
        'ultimo_run': ultimo_run,
        'gerado_em': datetime.now(timezone.utc).isoformat(),
    }
