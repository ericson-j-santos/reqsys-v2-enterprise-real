"""
hub_lowcode.py — Agrega dados de baixo código para o Hub: SharePoint, Power Automate, GitHub.

Todos os métodos degradam graciosamente quando as credenciais não estão configuradas,
retornando listas vazias com flag `configurado=False` em vez de lançar exceção.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.configuracao_lowcode import ConfiguracaoLowCode
from app.models.integracao_log import IntegracaoLog

logger = logging.getLogger('reqsys.hub_lowcode')

_GRAPH_TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
_GRAPH_BASE = 'https://graph.microsoft.com/v1.0'
_PA_TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
_PA_BASE = 'https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple'
_GH_BASE = 'https://api.github.com'
_TIERI_URL = 'https://orga258f260.crm2.dynamics.com'

_CHAVE_WEBHOOK_URL = 'planner_webhook_url'
_CHAVE_WEBHOOK_KEY = 'planner_webhook_key'
_CHAVE_TEAMS_WEBHOOK = 'teams_webhook_url'


def _tem_credenciais_graph() -> bool:
    return bool(settings.azure_tenant_id and settings.azure_client_id and settings.azure_client_secret)


async def _token_grafico() -> str:
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


async def _token_dataverse(instance_url: str) -> str:
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


# ---------------------------------------------------------------------------
# SharePoint / pacotes IA
# ---------------------------------------------------------------------------

async def listar_pacotes_ia(limit: int = 20) -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Power Automate / Dataverse flows
# ---------------------------------------------------------------------------

async def listar_flows_pa() -> dict[str, Any]:
    if not _tem_credenciais_graph():
        return {'configurado': False, 'flows': [], 'execucoes': [], 'erro': 'Credenciais Azure AD não configuradas'}

    try:
        token = await _token_dataverse(_TIERI_URL)
        headers = {'Authorization': f'Bearer {token}', 'OData-MaxVersion': '4.0', 'OData-Version': '4.0'}
        base = f'{_TIERI_URL}/api/data/v9.2'

        async with httpx.AsyncClient(timeout=15) as c:
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
        return {'configurado': True, 'flows': flows, 'execucoes': [], 'erro': None}

    except Exception as exc:
        logger.warning('hub_lowcode: erro ao ler flows via Dataverse: %s', exc)
        return {'configurado': True, 'flows': [], 'execucoes': [], 'erro': str(exc)}


async def listar_ambientes_powerplatform() -> dict[str, Any]:
    if not _tem_credenciais_graph():
        return {'configurado': False, 'ambientes': [], 'erro': 'Credenciais Azure AD não configuradas'}

    try:
        token = await _token_power_automate()
        headers = {'Authorization': f'Bearer {token}'}
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f'{_PA_BASE}/environments?api-version=2016-11-01',
                headers=headers,
            )
            resp.raise_for_status()
            raw = resp.json().get('value', [])

        ambientes = [
            {
                'id': e.get('name'),
                'nome': e.get('properties', {}).get('displayName', ''),
                'regiao': e.get('location', ''),
                'tipo': e.get('properties', {}).get('environmentSku', ''),
                'estado': e.get('properties', {}).get('provisioningState', ''),
            }
            for e in raw
        ]
        return {'configurado': True, 'ambientes': ambientes, 'erro': None}

    except Exception as exc:
        logger.warning('hub_lowcode: erro ao listar ambientes PA: %s', exc)
        return {'configurado': True, 'ambientes': [], 'erro': str(exc)}


# ---------------------------------------------------------------------------
# GitHub Actions
# ---------------------------------------------------------------------------

async def listar_runs_github(limit: int = 10) -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Planner webhook / configuração
# ---------------------------------------------------------------------------

def obter_planner_webhook_config(db: Session) -> dict[str, Any]:
    chaves = [_CHAVE_WEBHOOK_URL, _CHAVE_WEBHOOK_KEY, _CHAVE_TEAMS_WEBHOOK]
    result = db.execute(select(ConfiguracaoLowCode).where(ConfiguracaoLowCode.chave.in_(chaves)))
    rows = {r.chave: r.valor for r in result.scalars()}

    webhook_url = rows.get(_CHAVE_WEBHOOK_URL) or settings.powerautomate_planner_webhook_url
    teams_url = rows.get(_CHAVE_TEAMS_WEBHOOK) or settings.teams_notifications_webhook_url

    return {
        'webhook_url': webhook_url,
        'webhook_key': rows.get(_CHAVE_WEBHOOK_KEY) or settings.powerautomate_planner_webhook_key,
        'teams_webhook_url': teams_url,
        'configurado': bool(webhook_url),
        'teams_configurado': bool(teams_url),
    }


def salvar_planner_webhook_config(
    db: Session,
    webhook_url: str | None = None,
    webhook_key: str | None = None,
    teams_webhook_url: str | None = None,
) -> dict[str, Any]:
    pares: dict[str, str] = {}
    if webhook_url is not None:
        pares[_CHAVE_WEBHOOK_URL] = webhook_url
    if webhook_key is not None:
        pares[_CHAVE_WEBHOOK_KEY] = webhook_key
    if teams_webhook_url is not None:
        pares[_CHAVE_TEAMS_WEBHOOK] = teams_webhook_url

    for chave, valor in pares.items():
        existing = db.get(ConfiguracaoLowCode, chave)
        if existing:
            existing.valor = valor
        else:
            db.add(ConfiguracaoLowCode(chave=chave, valor=valor))

    db.commit()
    return {'salvo': list(pares.keys()), 'total': len(pares)}


# ---------------------------------------------------------------------------
# Publicar tarefas no Planner via PA flow
# ---------------------------------------------------------------------------

async def publicar_tarefas_planner(
    db: Session,
    tarefas_texto: str,
    autor: str = '',
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """
    Envia tarefas para o Power Automate flow HTTP que cria no Planner e notifica Teams.
    Cada linha de `tarefas_texto`: Titulo|Responsavel|AAAA-MM-DD|Bucket|Prioridade|Descricao
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    cfg = obter_planner_webhook_config(db)
    webhook_url = cfg.get('webhook_url') or ''

    if not webhook_url:
        salvar_log_integracao(
            db, tipo='planner', status='erro', autor=autor,
            mensagem='POWERAUTOMATE_PLANNER_WEBHOOK_URL não configurado',
            correlation_id=correlation_id,
        )
        return {'ok': False, 'erro': 'Webhook URL não configurado', 'correlation_id': correlation_id}

    teams_webhook_url = cfg.get('teams_webhook_url') or ''
    payload: dict[str, Any] = {'tarefas_texto': tarefas_texto, 'autor': autor, 'teams_webhook_url': teams_webhook_url}
    headers: dict[str, str] = {'Content-Type': 'application/json'}
    webhook_key = cfg.get('webhook_key') or ''
    if webhook_key:
        headers['x-webhook-key'] = webhook_key

    try:
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(webhook_url, json=payload, headers=headers)
            resp.raise_for_status()
            resposta = resp.json()

        criadas = resposta.get('criadas', 0)
        teams_notificado = resposta.get('teams_notificado', False)

        salvar_log_integracao(
            db, tipo='planner', status='sucesso', autor=autor,
            total=criadas, mensagem=f'{criadas} tarefa(s) criada(s) no Planner',
            detalhes={'teams_notificado': teams_notificado, 'flow_resposta': resposta},
            correlation_id=correlation_id,
        )

        return {
            'ok': True,
            'criadas': criadas,
            'teams_notificado': teams_notificado,
            'correlation_id': correlation_id,
            'flow_resposta': resposta,
        }

    except httpx.HTTPStatusError as exc:
        msg = f'Flow retornou HTTP {exc.response.status_code}'
        salvar_log_integracao(db, tipo='planner', status='erro', autor=autor,
                              mensagem=msg, correlation_id=correlation_id)
        return {'ok': False, 'erro': msg, 'correlation_id': correlation_id}

    except Exception as exc:
        msg = str(exc)
        salvar_log_integracao(db, tipo='planner', status='erro', autor=autor,
                              mensagem=msg, correlation_id=correlation_id)
        return {'ok': False, 'erro': msg, 'correlation_id': correlation_id}


# ---------------------------------------------------------------------------
# Descobrir planos Planner via Graph
# ---------------------------------------------------------------------------

async def descobrir_planos_planner(group_id: str) -> dict[str, Any]:
    if not _tem_credenciais_graph():
        return {'configurado': False, 'planos': [], 'erro': 'Credenciais Graph não configuradas'}

    try:
        token = await _token_grafico()
        headers = {'Authorization': f'Bearer {token}'}
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f'{_GRAPH_BASE}/groups/{group_id}/planner/plans',
                headers=headers,
            )
            resp.raise_for_status()
            raw = resp.json().get('value', [])

        planos = [{'id': p.get('id'), 'titulo': p.get('title', '')} for p in raw]
        return {'configurado': True, 'planos': planos, 'erro': None}

    except Exception as exc:
        logger.warning('hub_lowcode: erro ao descobrir planos: %s', exc)
        return {'configurado': True, 'planos': [], 'erro': str(exc)}


# ---------------------------------------------------------------------------
# Integração log
# ---------------------------------------------------------------------------

def _try_json(val: Any) -> str:
    if val is None:
        return '{}'
    if isinstance(val, str):
        return val
    try:
        return json.dumps(val, ensure_ascii=False, default=str)
    except Exception:
        return str(val)


def salvar_log_integracao(
    db: Session,
    tipo: str,
    status: str,
    autor: str = '',
    titulo: str = '',
    total: int = 0,
    mensagem: str = '',
    detalhes: Any = None,
    correlation_id: str = '',
) -> None:
    try:
        log = IntegracaoLog(
            tipo=tipo,
            status=status,
            autor=autor,
            titulo=titulo,
            total=total,
            mensagem=mensagem,
            detalhes=_try_json(detalhes),
            correlation_id=correlation_id or '',
        )
        db.add(log)
        db.commit()
    except Exception as exc:
        logger.warning('hub_lowcode: erro ao salvar log: %s', exc)


def listar_historico_integracoes(
    db: Session,
    tipo: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    try:
        q = select(IntegracaoLog).order_by(IntegracaoLog.criado_em.desc()).limit(limit)
        if tipo:
            q = q.where(IntegracaoLog.tipo == tipo)
        if status:
            q = q.where(IntegracaoLog.status == status)

        result = db.execute(q)
        rows = result.scalars().all()

        eventos = [
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
        return {'configurado': True, 'eventos': eventos, 'total': len(eventos), 'erro': None}

    except Exception as exc:
        logger.warning('hub_lowcode: erro ao listar histórico: %s', exc)
        return {'configurado': True, 'eventos': [], 'total': 0, 'erro': str(exc)}


# ---------------------------------------------------------------------------
# Testar webhook Teams
# ---------------------------------------------------------------------------

async def testar_teams_webhook(teams_webhook_url: str) -> dict[str, Any]:
    if not teams_webhook_url:
        return {'ok': False, 'erro': 'URL do webhook Teams não fornecida'}

    payload = {
        'type': 'message',
        'attachments': [
            {
                'contentType': 'application/vnd.microsoft.card.adaptive',
                'content': {
                    '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
                    'type': 'AdaptiveCard',
                    'version': '1.2',
                    'body': [
                        {
                            'type': 'TextBlock',
                            'size': 'Medium',
                            'weight': 'Bolder',
                            'text': 'ReqSys: Teste de notificacao',
                        },
                        {
                            'type': 'TextBlock',
                            'text': 'O webhook do ReqSys esta configurado corretamente.',
                            'wrap': True,
                        },
                    ],
                },
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(teams_webhook_url, json=payload)
            resp.raise_for_status()
            return {'ok': True, 'status': resp.status_code}
    except httpx.HTTPStatusError as exc:
        return {'ok': False, 'erro': f'HTTP {exc.response.status_code}: {exc.response.text[:300]}'}
    except Exception as exc:
        return {'ok': False, 'erro': str(exc)}
