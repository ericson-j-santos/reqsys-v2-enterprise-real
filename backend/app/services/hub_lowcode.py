"""
hub_lowcode.py — Agrega dados de baixo código para o Hub: SharePoint, Power Automate, GitHub.

Todos os métodos degradam graciosamente quando as credenciais não estão configuradas,
retornando listas vazias com flag `configurado=False` em vez de lançar exceção.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.configuracao_lowcode import ConfiguracaoLowCode
from app.models.integracao_log import IntegracaoLog
from app.schemas.planner import PlannerTaskIn

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
            f'&$orderby=lastModifiedDateTime desc'
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


async def _token_dataverse(instance_url: str) -> str:
    """Obtém access token para a Dataverse API via client_credentials."""
    scope = instance_url.rstrip('/') + '/.default'
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(
            _GRAPH_TOKEN_URL.format(tenant=settings.azure_tenant_id),
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.azure_client_id,
                'client_secret': settings.azure_client_secret,
                'scope': scope,
            },
        )
        resp.raise_for_status()
        return resp.json()['access_token']


# URL do ambiente tieri onde o flow vive
_TIERI_URL = 'https://orga258f260.crm2.dynamics.com'


async def listar_flows_pa() -> dict[str, Any]:
    """
    Lista flows ativos via Dataverse API (o SPN tem papel Administrador do Sistema lá).
    Lê execuções via flowsessions.
    Retorna: { configurado, flows, execucoes, erro }
    """
    if not _tem_credenciais_graph():
        return {'configurado': False, 'flows': [], 'execucoes': [], 'erro': 'Credenciais Azure AD não configuradas'}

    try:
        token = await _token_dataverse(_TIERI_URL)
        headers = {'Authorization': f'Bearer {token}', 'OData-MaxVersion': '4.0', 'OData-Version': '4.0'}
        base = f'{_TIERI_URL}/api/data/v9.2'

        async with httpx.AsyncClient(timeout=15) as c:
            # Flows ativos (category=5 = Modern Flow)
            r_flows = await c.get(
                f'{base}/workflows'
                f'?$filter=category eq 5 and statecode eq 1'
                f'&$select=workflowid,name,statecode,statuscode,createdon,modifiedon'
                f'&$top=20',
                headers=headers,
            )
            r_flows.raise_for_status()
            flows_raw = r_flows.json().get('value', [])

        flows = [
            {
                'id': f.get('workflowid'),
                'nome': f.get('name', ''),
                'estado': 'Started' if f.get('statuscode') == 2 else 'Stopped',
                'criado_em': f.get('createdon', ''),
                'modificado_em': f.get('modifiedon', ''),
            }
            for f in flows_raw
        ]

        # Execuções: flow acionado via PowerAppsV2 não grava em flowsessions no Dataverse.
        # Histórico disponível apenas no portal Power Automate.
        execucoes: list = []

        return {'configurado': True, 'flows': flows, 'execucoes': execucoes, 'erro': None}

    except Exception as exc:
        logger.warning('hub_lowcode: erro ao ler flows via Dataverse: %s', exc)
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


def obter_planner_webhook_config(db: Session) -> dict[str, str]:
    """Retorna url e key do webhook Planner salvo no DB (ou fallback em settings)."""
    url_row = db.query(ConfiguracaoLowCode).filter_by(chave='planner_webhook_url').first()
    key_row = db.query(ConfiguracaoLowCode).filter_by(chave='planner_webhook_key').first()
    url = (url_row.valor if url_row else '') or settings.powerautomate_planner_webhook_url
    key = (key_row.valor if key_row else '') or settings.powerautomate_planner_webhook_key
    return {
        'url': url,
        'key': key,
        'configurado': bool(url),
        'url_mascarada': (url[:30] + '...') if len(url) > 30 else url,
    }


def salvar_planner_webhook_config(db: Session, webhook_url: str, webhook_key: str = '') -> dict[str, Any]:
    """Persiste a URL e key do trigger HTTP do Power Automate no DB."""
    if not webhook_url.startswith('https://'):
        raise ValueError('webhook_url deve começar com https://')
    for chave, valor in [('planner_webhook_url', webhook_url), ('planner_webhook_key', webhook_key)]:
        row = db.query(ConfiguracaoLowCode).filter_by(chave=chave).first()
        if row:
            row.valor = valor
        else:
            db.add(ConfiguracaoLowCode(chave=chave, valor=valor))
    db.commit()
    return {'salvo': True, 'url_mascarada': (webhook_url[:30] + '...') if len(webhook_url) > 30 else webhook_url}


async def publicar_tarefas_planner(
    tarefas: list[PlannerTaskIn],
    autor: str,
    correlation_id: str | None,
    webhook_url: str,
    webhook_key: str,
) -> dict[str, Any]:
    """Envia tarefas formatadas para o flow Power Automate via HTTP trigger."""
    if not webhook_url:
        return {'enviado': False, 'mensagem': 'Webhook Planner não configurado — acesse Hub Low-Code → Configurar Webhook', 'flow': None, 'resposta_flow': None, 'teams_notificado': False}

    linhas = []
    for t in tarefas:
        campos = [t.titulo, t.responsavel, t.data_vencimento, t.bucket, t.prioridade, t.descricao]
        linhas.append('|'.join(campos))
    tarefas_texto = '\n'.join(linhas)

    payload = {'tarefas_texto': tarefas_texto, 'autor': autor or ''}
    headers = {'Content-Type': 'application/json'}
    if webhook_key:
        headers['X-Webhook-Key'] = webhook_key
    if correlation_id:
        headers['X-Correlation-Id'] = correlation_id

    async with httpx.AsyncClient(timeout=60) as c:
        resp = await c.post(webhook_url, json=payload, headers=headers)
        resp.raise_for_status()
        try:
            resposta_flow = resp.json()
        except Exception:
            resposta_flow = {'raw': resp.text}

    teams_notificado = bool(resposta_flow.get('teams_notificado')) if isinstance(resposta_flow, dict) else False
    criadas = resposta_flow.get('criadas', len(tarefas)) if isinstance(resposta_flow, dict) else len(tarefas)

    return {
        'enviado': True,
        'mensagem': f'{criadas} tarefa(s) criada(s) no Planner',
        'flow': resposta_flow.get('flow') if isinstance(resposta_flow, dict) else None,
        'criadas': criadas,
        'resposta_flow': resposta_flow,
        'teams_notificado': teams_notificado,
    }


async def listar_ambientes_powerplatform() -> dict[str, Any]:
    """Lista ambientes Power Platform disponíveis via API de administração."""
    if not _tem_credenciais_graph():
        return {'configurado': False, 'ambientes': [], 'erro': 'Credenciais Azure AD não configuradas'}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            token_resp = await c.post(
                _PA_TOKEN_URL.format(tenant=settings.azure_tenant_id),
                data={
                    'grant_type': 'client_credentials',
                    'client_id': settings.azure_client_id,
                    'client_secret': settings.azure_client_secret,
                    'scope': 'https://service.flow.microsoft.com/.default',
                },
            )
            token_resp.raise_for_status()
            token = token_resp.json()['access_token']
            resp = await c.get(
                f'{_PA_BASE}/environments?api-version=2016-11-01',
                headers={'Authorization': f'Bearer {token}'},
            )
            resp.raise_for_status()
            envs_raw = resp.json().get('value', [])
        ambientes = [
            {
                'id': e.get('name'),
                'nome': e.get('properties', {}).get('displayName', ''),
                'regiao': e.get('location', ''),
                'tipo': e.get('properties', {}).get('environmentSku', ''),
                'url': e.get('properties', {}).get('linkedEnvironmentMetadata', {}).get('instanceUrl', ''),
            }
            for e in envs_raw
        ]
        return {'configurado': True, 'ambientes': ambientes, 'erro': None}
    except Exception as exc:
        logger.warning('hub_lowcode: erro ao listar ambientes PA: %s', exc)
        return {'configurado': True, 'ambientes': [], 'erro': str(exc)}


async def descobrir_planner_no_ambiente(instance_url: str, filtro: str = 'Planner') -> dict[str, Any]:
    """Lista workflows Dataverse que contêm o filtro no nome."""
    if not _tem_credenciais_graph():
        return {'configurado': False, 'flows': [], 'erro': 'Credenciais Azure AD não configuradas'}
    try:
        token = await _token_dataverse(instance_url)
        headers = {'Authorization': f'Bearer {token}', 'OData-MaxVersion': '4.0', 'OData-Version': '4.0'}
        base = instance_url.rstrip('/') + '/api/data/v9.2'
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f"{base}/workflows?$filter=category eq 5 and contains(name,'{filtro}')&$select=workflowid,name,statecode,statuscode,createdon",
                headers=headers,
            )
            resp.raise_for_status()
            flows_raw = resp.json().get('value', [])
        flows = [
            {'id': f.get('workflowid'), 'nome': f.get('name'), 'estado': 'Ativo' if f.get('statecode') == 1 else 'Rascunho', 'criado_em': f.get('createdon')}
            for f in flows_raw
        ]
        return {'configurado': True, 'flows': flows, 'erro': None}
    except Exception as exc:
        return {'configurado': True, 'flows': [], 'erro': str(exc)}


def _try_json(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return s


def salvar_log_integracao(
    db: Session,
    tipo: str,
    status: str,
    titulo: str = '',
    autor: str = '',
    total: int = 0,
    mensagem: str = '',
    detalhes: dict | None = None,
    correlation_id: str = '',
) -> IntegracaoLog:
    entrada = IntegracaoLog(
        tipo=tipo, status=status, titulo=titulo, autor=autor, total=total,
        mensagem=mensagem,
        detalhes=json.dumps(detalhes or {}, ensure_ascii=False, default=str),
        correlation_id=correlation_id or '',
    )
    db.add(entrada)
    db.commit()
    db.refresh(entrada)
    return entrada


def listar_historico_integracoes(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.query(IntegracaoLog).order_by(IntegracaoLog.id.desc()).limit(limit).all()
    return [
        {
            'id': r.id,
            'criado_em': r.criado_em.isoformat() if r.criado_em else None,
            'tipo': r.tipo,
            'status': r.status,
            'titulo': r.titulo,
            'autor': r.autor,
            'total': r.total,
            'mensagem': r.mensagem,
            'detalhes': _try_json(r.detalhes),
            'correlation_id': r.correlation_id,
        }
        for r in rows
    ]
