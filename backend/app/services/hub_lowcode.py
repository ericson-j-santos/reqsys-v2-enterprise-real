"""
hub_lowcode.py — Agrega dados de baixo código para o Hub: SharePoint, Power Automate, GitHub.

Todos os métodos degradam graciosamente quando as credenciais não estão configuradas,
retornando listas vazias com flag `configurado=False` em vez de lançar exceção.
"""
import json
import logging
import uuid
from datetime import datetime, time, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    call_with_retry_async,
)
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
_FLOW_BOT_LIMITE_ACOES_DIA = 6000
_FLOW_BOT_ACOES_SUCESSO = 9
_FLOW_BOT_ACOES_ERRO = 3


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


async def token_power_automate() -> str:
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
        token = await token_power_automate()
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


def _try_parse_json(val: Any) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    if not isinstance(val, str) or not val.strip():
        return {}
    try:
        parsed = json.loads(val)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


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


def resumo_uso_flow_bot_hoje(
    db: Session,
    *,
    limite_acoes_dia: int = _FLOW_BOT_LIMITE_ACOES_DIA,
    agora: datetime | None = None,
) -> dict[str, Any]:
    """Calcula uso diario do flow_bot a partir do integracao_log.

    O flow real `robo_envia_teamsv1` foi contado em 2026-07-09:
    sucesso = 9 acoes; erro = 3 acoes.
    """
    try:
        agora_ref = agora or datetime.now(timezone.utc)
        inicio_dia = datetime.combine(agora_ref.date(), time.min, tzinfo=agora_ref.tzinfo)
        fim_dia = datetime.combine(agora_ref.date(), time.max, tzinfo=agora_ref.tzinfo)

        q = (
            select(IntegracaoLog)
            .where(IntegracaoLog.criado_em >= inicio_dia)
            .where(IntegracaoLog.criado_em <= fim_dia)
            .where(IntegracaoLog.tipo == 'teams_gateway')
            .order_by(IntegracaoLog.criado_em.desc())
        )
        rows = db.execute(q).scalars().all()

        por_dono: dict[str, dict[str, Any]] = {}
        total_mensagens = 0
        total_acoes = 0
        for row in rows:
            detalhes = _try_parse_json(row.detalhes)
            if detalhes.get('canal_usado') != 'flow_bot':
                continue

            total_mensagens += 1
            provider = _try_parse_json(detalhes.get('provider_response'))
            dono = (
                provider.get('owner')
                or detalhes.get('owner')
                or row.autor
                or 'env:TEAMS_FLOW_BOT_WEBHOOK_URL'
            )
            acoes = _FLOW_BOT_ACOES_SUCESSO if row.status == 'sucesso' else _FLOW_BOT_ACOES_ERRO
            item = por_dono.setdefault(
                dono,
                {
                    'dono': dono,
                    'mensagens': 0,
                    'sucessos': 0,
                    'erros': 0,
                    'acoes_usadas': 0,
                    'limite_acoes_dia': limite_acoes_dia,
                    'percentual_usado': 0,
                    'mensagens_restantes_estimadas': 0,
                },
            )
            item['mensagens'] += 1
            item['sucessos'] += 1 if row.status == 'sucesso' else 0
            item['erros'] += 1 if row.status != 'sucesso' else 0
            item['acoes_usadas'] += acoes
            total_acoes += acoes

        for item in por_dono.values():
            restante = max(limite_acoes_dia - item['acoes_usadas'], 0)
            item['percentual_usado'] = round((item['acoes_usadas'] / limite_acoes_dia) * 100, 1) if limite_acoes_dia else 0
            item['mensagens_restantes_estimadas'] = restante // _FLOW_BOT_ACOES_SUCESSO

        owners = sorted(por_dono.values(), key=lambda item: item['acoes_usadas'], reverse=True)
        capacidade_total = limite_acoes_dia * max(len(owners), 1)
        return {
            'configurado': True,
            'data': agora_ref.date().isoformat(),
            'janela_inicio': inicio_dia.isoformat(),
            'janela_fim': fim_dia.isoformat(),
            'limite_acoes_dia_por_dono': limite_acoes_dia,
            'acoes_por_mensagem_sucesso': _FLOW_BOT_ACOES_SUCESSO,
            'acoes_por_mensagem_erro': _FLOW_BOT_ACOES_ERRO,
            'mensagens': total_mensagens,
            'acoes_usadas': total_acoes,
            'capacidade_acoes_total_estimado': capacidade_total,
            'percentual_usado_total': round((total_acoes / capacidade_total) * 100, 1) if capacidade_total else 0,
            'mensagens_restantes_estimadas': max(capacidade_total - total_acoes, 0) // _FLOW_BOT_ACOES_SUCESSO,
            'owners': owners,
            'erro': None,
        }

    except Exception as exc:
        logger.warning('hub_lowcode: erro ao calcular uso flow_bot: %s', exc)
        return {'configurado': True, 'owners': [], 'mensagens': 0, 'acoes_usadas': 0, 'erro': str(exc)}


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


# ---------------------------------------------------------------------------
# Teams via Graph API — mensagens em chat 1:1/grupo
#
# Descoberta validada ao vivo (2026-07-07) contra o tenant real: o Graph NAO
# permite enviar chatMessage app-only (client credentials) para um chat entre
# humanos — mesmo com `Chat.ReadWrite.All` + `Chat.Create` (aplicacao) concedidos
# e a criacao do chat funcionando, o POST de mensagem retorna 403 exigindo
# `Teamwork.Migrate.All` (permissao de migracao/compliance, nao de mensageria).
# Isso so e contornavel publicando um Teams App/bot com RSC instalado na
# conversa — um projeto a parte, fora de escopo aqui.
#
# Por isso o envio real de mensagem usa o fluxo DELEGADO (on-behalf-of do
# usuario logado): o frontend adquire um access_token do Graph com escopo
# `ChatMessage.Send`/`Chat.ReadWrite` (ja concedidos via admin consent no app
# registration) e o backend apenas relaya essa chamada, sem client secret.
# `criar_chat_individual_teams` app-only continua funcional para CRIAR chats
# (isso nao tem a mesma restricao), mas enviar mensagem nele exige o token
# delegado — nao ha combinacao de permissao de aplicacao que resolva o envio.
# ---------------------------------------------------------------------------

_TEAMS_GRAPH_MAX_RETRIES = 3
_TEAMS_GRAPH_RETRY_BACKOFF_SECONDS = 0.5
_teams_graph_circuit = CircuitBreaker(name='teams_graph', failure_threshold=3, cooldown_seconds=60)


def reset_teams_graph_circuit_breaker() -> None:
    """Reseta o circuit breaker do Teams Graph (uso em testes)."""
    _teams_graph_circuit.reset()


def _normalizar_content_type_teams(content_type: str) -> str:
    return content_type if content_type in ('text', 'html') else 'text'


async def _postar_mensagem_chat_graph(
    chat_id: str,
    texto: str,
    tipo_conteudo: str,
    access_token: str,
) -> dict[str, Any]:
    payload = {'body': {'contentType': tipo_conteudo, 'content': texto}}

    async def _enviar() -> dict[str, Any]:
        headers = {'Authorization': f'Bearer {access_token}'}
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(f'{_GRAPH_BASE}/chats/{chat_id}/messages', json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    return await call_with_retry_async(
        _enviar,
        max_retries=_TEAMS_GRAPH_MAX_RETRIES,
        backoff_seconds=_TEAMS_GRAPH_RETRY_BACKOFF_SECONDS,
        retry_on=(httpx.TimeoutException, httpx.ConnectError),
        circuit=_teams_graph_circuit,
    )


async def enviar_mensagem_chat_teams(
    chat_id: str,
    texto: str,
    content_type: str = 'text',
    db: Session | None = None,
    autor: str = '',
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Envia mensagem app-only a um chat do Teams via Microsoft Graph.

    Aviso: o Graph bloqueia esse caminho para chats entre humanos (ver nota
    acima) — mantido para chats onde o proprio app seja participante (ex.:
    grupos criados incluindo um Teams App instalado). Para enviar a um chat
    humano-humano use `enviar_mensagem_chat_teams_como_usuario`.
    """
    corr = correlation_id or str(uuid.uuid4())
    if not _tem_credenciais_graph():
        erro = 'Credenciais Graph (AZURE_TENANT_ID/AZURE_CLIENT_ID/AZURE_CLIENT_SECRET) não configuradas'
        if db is not None:
            salvar_log_integracao(db, tipo='teams_graph', status='erro', autor=autor,
                                  mensagem=erro, correlation_id=corr)
        return {'configurado': False, 'enviado': False, 'erro': erro, 'correlation_id': corr}

    if not chat_id:
        return {'configurado': True, 'enviado': False, 'erro': 'chat_id não fornecido', 'correlation_id': corr}

    tipo_conteudo = _normalizar_content_type_teams(content_type)

    try:
        token = await _token_grafico()
        resposta = await _postar_mensagem_chat_graph(chat_id, texto, tipo_conteudo, token)
        if db is not None:
            salvar_log_integracao(
                db, tipo='teams_graph', status='sucesso', autor=autor,
                titulo=f'Mensagem enviada ao chat {chat_id}',
                mensagem=texto[:200],
                detalhes={'chat_id': chat_id, 'content_type': tipo_conteudo, 'message_id': resposta.get('id')},
                correlation_id=corr,
            )
        return {
            'configurado': True,
            'enviado': True,
            'message_id': resposta.get('id'),
            'chat_id': chat_id,
            'correlation_id': corr,
        }
    except CircuitBreakerOpenError as exc:
        msg = str(exc)
        if db is not None:
            salvar_log_integracao(db, tipo='teams_graph', status='erro', autor=autor, mensagem=msg, correlation_id=corr)
        return {'configurado': True, 'enviado': False, 'erro': msg, 'correlation_id': corr}
    except httpx.HTTPStatusError as exc:
        msg = f'HTTP {exc.response.status_code}: {exc.response.text[:300]}'
        if db is not None:
            salvar_log_integracao(db, tipo='teams_graph', status='erro', autor=autor, mensagem=msg, correlation_id=corr)
        return {'configurado': True, 'enviado': False, 'erro': msg, 'correlation_id': corr}
    except Exception as exc:
        msg = str(exc)
        if db is not None:
            salvar_log_integracao(db, tipo='teams_graph', status='erro', autor=autor, mensagem=msg, correlation_id=corr)
        return {'configurado': True, 'enviado': False, 'erro': msg, 'correlation_id': corr}


async def enviar_mensagem_chat_teams_como_usuario(
    chat_id: str,
    texto: str,
    usuario_access_token: str,
    content_type: str = 'text',
    db: Session | None = None,
    autor: str = '',
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Envia mensagem a um chat do Teams usando um access_token delegado do Graph
    (adquirido pelo frontend com o usuario logado, escopo ChatMessage.Send/
    Chat.ReadWrite). O backend nunca ve a senha/credencial do usuario, apenas
    relaya o token recebido — nao usa client secret nesta chamada.
    """
    corr = correlation_id or str(uuid.uuid4())
    if not usuario_access_token:
        return {'enviado': False, 'erro': 'usuario_access_token não fornecido', 'correlation_id': corr}
    if not chat_id:
        return {'enviado': False, 'erro': 'chat_id não fornecido', 'correlation_id': corr}

    tipo_conteudo = _normalizar_content_type_teams(content_type)

    try:
        resposta = await _postar_mensagem_chat_graph(chat_id, texto, tipo_conteudo, usuario_access_token)
        if db is not None:
            salvar_log_integracao(
                db, tipo='teams_graph_delegado', status='sucesso', autor=autor,
                titulo=f'Mensagem enviada ao chat {chat_id} (delegado)',
                mensagem=texto[:200],
                detalhes={'chat_id': chat_id, 'content_type': tipo_conteudo, 'message_id': resposta.get('id')},
                correlation_id=corr,
            )
        return {'enviado': True, 'message_id': resposta.get('id'), 'chat_id': chat_id, 'correlation_id': corr}
    except CircuitBreakerOpenError as exc:
        msg = str(exc)
        if db is not None:
            salvar_log_integracao(db, tipo='teams_graph_delegado', status='erro', autor=autor, mensagem=msg, correlation_id=corr)
        return {'enviado': False, 'erro': msg, 'correlation_id': corr}
    except httpx.HTTPStatusError as exc:
        msg = f'HTTP {exc.response.status_code}: {exc.response.text[:300]}'
        if db is not None:
            salvar_log_integracao(db, tipo='teams_graph_delegado', status='erro', autor=autor, mensagem=msg, correlation_id=corr)
        return {'enviado': False, 'erro': msg, 'correlation_id': corr}
    except Exception as exc:
        msg = str(exc)
        if db is not None:
            salvar_log_integracao(db, tipo='teams_graph_delegado', status='erro', autor=autor, mensagem=msg, correlation_id=corr)
        return {'enviado': False, 'erro': msg, 'correlation_id': corr}


def _extrair_membros_chat(chat: dict[str, Any]) -> list[dict[str, Any]]:
    membros = []
    for m in chat.get('members') or []:
        membros.append({
            'user_id': m.get('userId'),
            'nome': m.get('displayName') or '',
            'email': m.get('email') or '',
        })
    return membros


async def listar_chats_como_usuario(
    usuario_access_token: str,
    top: int = 50,
) -> dict[str, Any]:
    """Lista os chats (1:1 e grupo) do usuario logado via Graph, usando o
    access_token delegado (escopo Chat.Read/Chat.ReadWrite — ja concedido, sem
    permissao nova). Usado para preencher o seletor de chat_id no frontend em
    vez do usuario ter que descobrir/colar o id manualmente.
    """
    if not usuario_access_token:
        return {'chats': [], 'erro': 'usuario_access_token não fornecido'}

    async def _listar() -> dict[str, Any]:
        headers = {'Authorization': f'Bearer {usuario_access_token}'}
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f'{_GRAPH_BASE}/me/chats',
                params={'$top': top, '$expand': 'members'},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

    try:
        resposta = await call_with_retry_async(
            _listar,
            max_retries=_TEAMS_GRAPH_MAX_RETRIES,
            backoff_seconds=_TEAMS_GRAPH_RETRY_BACKOFF_SECONDS,
            retry_on=(httpx.TimeoutException, httpx.ConnectError),
            circuit=_teams_graph_circuit,
        )
        chats = [
            {
                'id': item.get('id'),
                'topico': item.get('topic'),
                'tipo': item.get('chatType'),
                'membros': _extrair_membros_chat(item),
            }
            for item in resposta.get('value', [])
        ]
        return {'chats': chats}
    except CircuitBreakerOpenError as exc:
        return {'chats': [], 'erro': str(exc)}
    except httpx.HTTPStatusError as exc:
        return {'chats': [], 'erro': f'HTTP {exc.response.status_code}: {exc.response.text[:300]}'}
    except Exception as exc:
        return {'chats': [], 'erro': str(exc)}


async def criar_chat_individual_teams(
    usuario_a_aad_object_id: str,
    usuario_b_aad_object_id: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Cria (ou obtem, se ja existir) um chat 1:1 app-only entre dois usuarios reais.

    Validado ao vivo (2026-07-07): o Graph so aceita 2 usuarios reais no roster
    de um chat oneOnOne — o service principal do proprio app NAO pode ser um dos
    membros (retorna 403 RosterCreationNotAllowed), entao esta funcao exige os
    dois AAD object IDs explicitamente. A criacao em si e idempotente por
    conjunto de membros: se ja existir um chat com os mesmos dois membros, a
    API retorna o chat existente em vez de duplicar. Enviar mensagem NESSE chat
    ainda exige o fluxo delegado (`enviar_mensagem_chat_teams_como_usuario`) —
    ver nota no topo da secao.
    """
    corr = correlation_id or str(uuid.uuid4())
    if not _tem_credenciais_graph():
        return {
            'configurado': False,
            'ok': False,
            'erro': 'Credenciais Graph (AZURE_TENANT_ID/AZURE_CLIENT_ID/AZURE_CLIENT_SECRET) não configuradas',
            'correlation_id': corr,
        }

    if not usuario_a_aad_object_id or not usuario_b_aad_object_id:
        return {
            'configurado': True, 'ok': False,
            'erro': 'usuario_a_aad_object_id e usuario_b_aad_object_id são obrigatórios',
            'correlation_id': corr,
        }

    payload = {
        'chatType': 'oneOnOne',
        'members': [
            {
                '@odata.type': '#microsoft.graph.aadUserConversationMember',
                'roles': ['owner'],
                'user@odata.bind': f"https://graph.microsoft.com/v1.0/users('{usuario_a_aad_object_id}')",
            },
            {
                '@odata.type': '#microsoft.graph.aadUserConversationMember',
                'roles': ['owner'],
                'user@odata.bind': f"https://graph.microsoft.com/v1.0/users('{usuario_b_aad_object_id}')",
            },
        ],
    }

    async def _criar() -> dict[str, Any]:
        token = await _token_grafico()
        headers = {'Authorization': f'Bearer {token}'}
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(f'{_GRAPH_BASE}/chats', json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    try:
        resposta = await call_with_retry_async(
            _criar,
            max_retries=_TEAMS_GRAPH_MAX_RETRIES,
            backoff_seconds=_TEAMS_GRAPH_RETRY_BACKOFF_SECONDS,
            retry_on=(httpx.TimeoutException, httpx.ConnectError),
            circuit=_teams_graph_circuit,
        )
        return {'configurado': True, 'ok': True, 'chat_id': resposta.get('id'), 'correlation_id': corr}
    except CircuitBreakerOpenError as exc:
        return {'configurado': True, 'ok': False, 'erro': str(exc), 'correlation_id': corr}
    except httpx.HTTPStatusError as exc:
        return {
            'configurado': True, 'ok': False,
            'erro': f'HTTP {exc.response.status_code}: {exc.response.text[:300]}',
            'correlation_id': corr,
        }
    except Exception as exc:
        return {'configurado': True, 'ok': False, 'erro': str(exc), 'correlation_id': corr}


async def criar_chat_e_enviar_como_usuario(
    usuario_a_aad_object_id: str,
    usuario_b_aad_object_id: str,
    texto: str,
    usuario_access_token: str,
    content_type: str = 'text',
    db: Session | None = None,
    autor: str = '',
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Cria/obtem o chat 1:1 entre os dois usuarios (app-only — funciona) e envia
    a mensagem usando o access_token delegado do usuario logado (unico caminho
    que o Graph aceita para postar em chat humano-humano, ver nota no topo).
    """
    corr = correlation_id or str(uuid.uuid4())
    chat = await criar_chat_individual_teams(usuario_a_aad_object_id, usuario_b_aad_object_id, correlation_id=corr)
    if not chat.get('ok'):
        if db is not None and chat.get('configurado'):
            salvar_log_integracao(db, tipo='teams_graph', status='erro', autor=autor,
                                  mensagem=chat.get('erro', 'falha ao criar chat 1:1'), correlation_id=corr)
        return {
            'configurado': chat.get('configurado', False),
            'enviado': False,
            'erro': chat.get('erro'),
            'correlation_id': corr,
        }

    return await enviar_mensagem_chat_teams_como_usuario(
        chat['chat_id'], texto, usuario_access_token,
        content_type=content_type, db=db, autor=autor, correlation_id=corr,
    )
