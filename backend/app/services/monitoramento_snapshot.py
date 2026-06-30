from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.monitoramento_operacional import (
    ItemMonitorado,
    MonitoramentoOperacional,
    ResumoMonitoramento,
)
from app.services.actions_runtime_monitor import GitHubActionsClient, classificar_runs
from app.services.connection_broker import listar_conectores, resumo_conectores


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


def _estado_govbi(db: Session | None = None) -> tuple[str, dict[str, Any]]:
    detalhes: dict[str, Any] = {'fonte': 'reqsys-proxy-local'}
    try:
        if db is None:
            from app.db import SessionLocal

            with SessionLocal() as session:
                return _estado_govbi(session)

        from app.models.requisito import Requisito
        from app.services.govbi_local_analytics import executar_analitico_local

        total = db.query(Requisito).count()
        probe = executar_analitico_local(db, 'total de requisitos', 'monitoramento-probe')
        detalhes.update(
            {
                'analitico_local': 'disponivel' if probe else 'indisponivel',
                'requisitos_indexados': total,
                'probe_status': probe.get('statusFluxo') if probe else None,
            }
        )
        if probe and probe.get('statusFluxo') == 'CONCLUIDO':
            return 'verde', detalhes
        if total > 0:
            return 'amarelo', detalhes
        return 'amarelo', {**detalhes, 'motivo': 'banco sem requisitos para analítico local'}
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
            detalhes={'motivo': 'snapshot dinâmico ativo', 'modo_coleta': modo_coleta},
        ),
        ItemMonitorado(
            tipo='integracao',
            referencia='REQSYS-OPER-001',
            titulo='GovBI IA',
            estado=estado_govbi,
            severidade='alta' if estado_govbi == 'vermelho' else 'media',
            origem='govbi-probe',
            detalhes=sinal_govbi,
        ),
        ItemMonitorado(
            tipo='frontend',
            referencia='REQSYS-OPER-002',
            titulo='Dashboard para Analitico filtrado',
            estado='verde',
            severidade='baixa',
            origem='reqsys-frontend',
            detalhes={'motivo': 'drill-down e filtros via query string em RequisitosView'},
        ),
        ItemMonitorado(
            tipo='integracao',
            referencia='REQSYS-OPER-003',
            titulo='Planner via Low Code e API',
            estado=estado_conectores,
            severidade='alta' if estado_conectores == 'vermelho' else 'media',
            origem='connection-broker',
            detalhes={'conectores': len(listar_conectores()), **sinal_conectores},
        ),
        ItemMonitorado(
            tipo='pipeline',
            referencia='REQSYS-OPER-004',
            titulo='Pipeline operacional e CI',
            estado=estado_ci,
            severidade='critica' if estado_ci == 'vermelho' else 'media',
            origem='github-actions' if sinal_ci.get('modo') == 'live' else 'github-actions-preview',
            detalhes=sinal_ci,
        ),
        ItemMonitorado(
            tipo='gate',
            referencia='production-gates',
            titulo='Gates obrigatorios de producao',
            estado='verde',
            severidade='critica',
            origem='reqsys',
            detalhes={'validacao': 'configuracoes inseguras bloqueiam producao'},
        ),
        ItemMonitorado(
            tipo='aop',
            referencia='AOP-P0-1',
            titulo='Autonomous Operations Platform - maturidade e politicas governadas',
            estado='amarelo',
            severidade='critica',
            origem='incremento-operacao-autonoma',
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
        ),
        itens=itens,
    )
