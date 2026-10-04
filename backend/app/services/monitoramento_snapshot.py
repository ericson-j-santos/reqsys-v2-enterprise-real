from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import GovBIConfigurationError, settings, validate_govbi_base_url
from app.schemas.monitoramento_operacional import (
    ItemMonitorado,
    MonitoramentoOperacional,
    ResumoMonitoramento,
    TempoOperacional,
)
from app.services.actions_runtime_monitor import GitHubActionsClient, classificar_runs
from app.services.connection_broker import listar_conectores, resumo_conectores


def _govbi_base_url() -> str:
    return validate_govbi_base_url(getattr(settings, 'govbi_base_url', ''))


def _govbi_timeout() -> float:
    return float(getattr(settings, 'govbi_timeout_seconds', 15.0) or 15.0)


def classificar_estado_geral(itens: list[ItemMonitorado]) -> str:
    if not itens:
        return 'desconhecido'
    if any(item.estado == 'bloqueado' or item.bloqueante for item in itens):
        return 'bloqueado'
    if any(item.estado == 'vermelho' for item in itens):
        return 'vermelho'
    if any(item.estado in {'amarelo', 'desconhecido'} for item in itens):
        return 'amarelo'
    return 'verde'


def criar_tempo_operacional(estado_geral: str) -> TempoOperacional:
    if estado_geral == 'bloqueado':
        return TempoOperacional(
            previsao_proxima_acao='Tratar bloqueio operacional prioritario antes de avancar.',
            eta_proxima_verificacao_minutos=10,
            tempo_medio_proxima_acao_minutos=15,
            tempo_medio_resolucao_horas=4.0,
            tempo_medio_review_minutos=30,
            sla_operacional_minutos=60,
        )
    if estado_geral in {'vermelho', 'amarelo'}:
        return TempoOperacional(
            previsao_proxima_acao='Revalidar verificacoes automaticas, revisao e pendencias antes de prosseguir.',
            eta_proxima_verificacao_minutos=15,
            tempo_medio_proxima_acao_minutos=20,
            tempo_medio_resolucao_horas=6.0,
            tempo_medio_review_minutos=45,
            sla_operacional_minutos=120,
        )
    return TempoOperacional(
        previsao_proxima_acao='Manter monitoramento e preparar a proxima frente segura.',
        eta_proxima_verificacao_minutos=30,
        tempo_medio_proxima_acao_minutos=30,
        tempo_medio_resolucao_horas=2.0,
        tempo_medio_review_minutos=20,
        sla_operacional_minutos=240,
    )


def _estado_de_score(score: float) -> str:
    if score >= 95:
        return 'verde'
    if score >= 80:
        return 'amarelo'
    return 'vermelho'


def _estado_conectores() -> tuple[str, dict[str, Any]]:
    resumo = resumo_conectores()
    estado = resumo['estado_geral']
    if estado == 'bloqueado':
        return 'vermelho', resumo
    if estado == 'amarelo':
        return 'amarelo', resumo
    if estado == 'verde':
        return 'verde', resumo
    return 'desconhecido', resumo


def _estado_govbi() -> tuple[str, dict[str, Any]]:
    try:
        base_url = _govbi_base_url()
    except GovBIConfigurationError as exc:
        return 'bloqueado', {
            'base_url': None,
            'fonte': 'configuracao',
            'modo': 'bloqueado',
            'motivo': str(exc),
        }

    detalhes: dict[str, Any] = {'base_url': base_url, 'fonte': 'probe-http'}
    try:
        with httpx.Client(timeout=min(_govbi_timeout(), 5.0)) as client:
            response = client.get(f'{base_url}/health')
        detalhes['http_status'] = response.status_code
        if response.status_code < 500:
            return 'verde', detalhes
        return 'amarelo', detalhes
    except Exception as exc:  # noqa: BLE001 - sinal operacional
        detalhes['erro'] = f'{type(exc).__name__}'
        return 'vermelho', detalhes


def _estado_ci() -> tuple[str, dict[str, Any]]:
    token = os.getenv('GITHUB_TOKEN') or os.getenv('REQSYS_GITHUB_TOKEN')
    repo = os.getenv('REQSYS_GITHUB_REPO') or os.getenv('GITHUB_REPOSITORY')
    detalhes: dict[str, Any] = {'fonte': 'github-actions', 'repo': repo or None}
    if not token or not repo:
        detalhes['motivo'] = 'GITHUB_TOKEN ou REQSYS_GITHUB_REPO ausente'
        detalhes['modo'] = 'preview'
        return 'amarelo', detalhes
    try:
        client = GitHubActionsClient(token=token)
        runs = client.listar_runs(repo=repo, branch='main', per_page=10)
        resumo = classificar_runs(runs)
        detalhes.update(
            {
                'modo': 'live',
                'score_saude': resumo['score_saude'],
                'decisao': resumo['decisao'],
                'total_runs': resumo['total_runs'],
                'falhas': len(resumo['falhas']),
            }
        )
        if resumo['falhas']:
            return 'vermelho', detalhes
        if resumo['em_execucao']:
            return 'amarelo', detalhes
        return _estado_de_score(float(resumo['score_saude'])), detalhes
    except Exception as exc:  # noqa: BLE001 - sinal operacional
        detalhes['erro'] = f'{type(exc).__name__}'
        detalhes['modo'] = 'preview'
        return 'amarelo', detalhes


def _resolver_modo_coleta(sinais: dict[str, dict[str, Any]]) -> str:
    modos = {sinal.get('modo', 'live') for sinal in sinais.values()}
    if modos == {'live'}:
        return 'live'
    if 'live' in modos:
        return 'hibrido'
    return 'preview'


def criar_snapshot_operacional(correlation_id: str) -> MonitoramentoOperacional:
    estado_govbi, sinal_govbi = _estado_govbi()
    estado_ci, sinal_ci = _estado_ci()
    estado_conectores, sinal_conectores = _estado_conectores()
    sinais = {
        'govbi': sinal_govbi,
        'ci': sinal_ci,
        'conectores': sinal_conectores,
    }
    modo_coleta = _resolver_modo_coleta(sinais)

    itens = [
        ItemMonitorado(
            tipo='frente',
            referencia='REQSYS-OPER-005',
            titulo='Implementar monitoramento operacional',
            estado='verde' if modo_coleta != 'preview' else 'amarelo',
            severidade='media',
            origem='monitoramento-snapshot-v2',
            pronto_para_merge=modo_coleta != 'preview',
            proximo_passo='Manter coleta dinamica e evidencias operacionais atualizadas.',
            criterio_de_fechamento='Snapshot dinamico ativo com coleta fora do modo preview.',
            detalhes={'motivo': 'snapshot dinâmico ativo', 'modo_coleta': modo_coleta},
        ),
        ItemMonitorado(
            tipo='integracao',
            referencia='REQSYS-OPER-001',
            titulo='GovBI IA',
            estado=estado_govbi,
            severidade='alta' if estado_govbi == 'vermelho' else 'media',
            origem='govbi-probe',
            bloqueante=estado_govbi == 'bloqueado',
            proximo_passo='Validar fonte do GovBI, disponibilidade e falha controlada antes de promover o estado.',
            criterio_de_fechamento='Probe GovBI responde de forma valida e configuracao obrigatoria esta presente.',
            detalhes=sinal_govbi,
        ),
        ItemMonitorado(
            tipo='frontend',
            referencia='REQSYS-OPER-002',
            titulo='Painel Analítico com filtros',
            estado='verde',
            severidade='baixa',
            origem='reqsys-frontend',
            pronto_para_merge=True,
            proximo_passo='Preservar deep link e filtros em testes de regressao do frontend.',
            criterio_de_fechamento='Cards continuam abrindo o analitico com filtros preservados na URL.',
            detalhes={'motivo': 'drill-down e filtros via query string em RequisitosView'},
        ),
        ItemMonitorado(
            tipo='integracao',
            referencia='REQSYS-OPER-003',
            titulo='Planner via Low Code e API',
            estado=estado_conectores,
            severidade='alta' if estado_conectores == 'vermelho' else 'media',
            origem='connection-broker',
            proximo_passo='Revalidar conectores, idempotencia e reprocessamento quando houver falha.',
            criterio_de_fechamento='Conectores ficam verdes e reenvio controlado nao duplica efeito externo.',
            detalhes={'conectores': len(listar_conectores()), **sinal_conectores},
        ),
        ItemMonitorado(
            tipo='pipeline',
            referencia='REQSYS-OPER-004',
            titulo='Esteira operacional e CI',
            estado=estado_ci,
            severidade='critica' if estado_ci == 'vermelho' else 'media',
            origem='github-actions' if sinal_ci.get('modo') == 'live' else 'github-actions-preview',
            proximo_passo='Manter os gates obrigatorios verdes no HEAD atual e publicar evidencias do CI.',
            criterio_de_fechamento='CI obrigatorio fica verde no SHA atual sem bypass de cobertura ou seguranca.',
            detalhes=sinal_ci,
        ),
        ItemMonitorado(
            tipo='gate',
            referencia='production-gates',
            titulo='Gates obrigatorios de producao',
            estado='verde',
            severidade='critica',
            origem='reqsys',
            pronto_para_merge=True,
            criterio_de_fechamento='Configuracoes inseguras continuam bloqueando inicializacao em producao.',
            detalhes={'validacao': 'configuracoes inseguras bloqueiam producao'},
        ),
        ItemMonitorado(
            tipo='aop',
            referencia='AOP-P0-1',
            titulo='Autonomous Operations Platform - maturidade e politicas governadas',
            estado='amarelo',
            severidade='critica',
            origem='incremento-operacao-autonoma',
            proximo_passo='Evoluir maturidade sem liberar execucao destrutiva fora da politica governada.',
            criterio_de_fechamento='Maturidade e politicas possuem evidencia e qualquer mutacao destrutiva permanece governada.',
            detalhes={
                'motivo': 'maturity score e policies implementadas; execucao destrutiva permanece bloqueada por governanca',
                'endpoint': '/operacao-autonoma/maturidade',
            },
        ),
        ItemMonitorado(
            tipo='aop',
            referencia='AOP-P0-2',
            titulo='Runtime Health Validator e Executor Governado de Remediacao',
            estado='amarelo',
            severidade='critica',
            origem='incremento-operacao-autonoma',
            proximo_passo='Validar health e remediacao dry-run antes de qualquer ampliacao de efeito.',
            criterio_de_fechamento='Health validator e remediacao governada possuem evidencias atuais sem bypass de politica.',
            detalhes={
                'motivo': 'health validator e executor dry-run implementados; acoes destrutivas seguem bloqueadas por politica',
                'endpoints': ['/operacao-autonoma/runtime-health', '/operacao-autonoma/remediacoes/avaliar'],
            },
        ),
    ]

    estado_geral = classificar_estado_geral(itens)
    return MonitoramentoOperacional(
        correlation_id=correlation_id,
        coletado_em=datetime.now(UTC).isoformat(),
        ambiente=settings.normalized_environment,
        modo_coleta=modo_coleta,
        coleta_detalhes={
            'sinais': sinais,
            'preview': modo_coleta == 'preview',
            'mensagem': (
                'Snapshot em modo preview: configure GITHUB_TOKEN e REQSYS_GITHUB_REPO para telemetria CI live.'
                if modo_coleta == 'preview'
                else 'Snapshot composto a partir de sinais operacionais live e/ou registry local.'
            ),
        },
        resumo=ResumoMonitoramento(
            estado_geral=estado_geral,
            bloqueios=sum(1 for item in itens if item.estado == 'bloqueado' or item.bloqueante),
            pendencias=sum(1 for item in itens if item.estado in {'amarelo', 'vermelho', 'desconhecido'}),
            total_itens=len(itens),
            frentes_criticas=sum(1 for item in itens if item.severidade == 'critica'),
            itens_prontos_para_merge=sum(1 for item in itens if item.pronto_para_merge),
        ),
        tempo_operacional=criar_tempo_operacional(estado_geral),
        itens=itens,
    )
