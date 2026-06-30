from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.requisito import Requisito


def _texto(pergunta: str) -> str:
    return (pergunta or '').strip().lower()


def _extrair_ano(pergunta: str) -> int | None:
    match = re.search(r'(20\d{2})', pergunta)
    return int(match.group(1)) if match else None


def _mes_label(dt: datetime | None) -> str:
    if dt is None:
        return 'sem_data'
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.strftime('%Y-%m')


def _resposta_local(
    *,
    pergunta: str,
    correlation_id: str,
    metrica: str,
    dimensoes: list[str],
    colunas: list[str],
    linhas: list[dict[str, Any]],
    sql: str,
    filtros: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        'avisos': [
            'Consulta executada pelo analítico local ReqSys (SQLite operacional).',
            'GovBI externo indisponível ou sem métrica compatível; dados reais do banco local.',
        ],
        'nivelSensibilidade': 'BAIXA',
        'statusFluxo': 'CONCLUIDO',
        'metrica': metrica,
        'dimensoes': dimensoes,
        'filtros': filtros or {},
        'correlationId': correlation_id,
        'sqlGerado': sql,
        'fonteAnalitica': 'reqsys-sqlite',
        'resultado': {'colunas': colunas, 'linhas': linhas},
        'mascaramentoAplicado': True,
        'requerAprovacao': False,
        'aprovacaoId': None,
        'explicacao': 'Analítico local ReqSys sobre tabela requisitos — dados operacionais reais.',
    }


def executar_analitico_local(db: Session, pergunta: str, correlation_id: str) -> dict[str, Any] | None:
    """Responde perguntas sobre requisitos usando o SQLite operacional."""
    texto = _texto(pergunta)
    if not any(token in texto for token in ('requisit', 'proposta', 'status', 'situa', 'unidade', 'area', 'área', 'total', 'quant', 'contagem', 'mês', 'mes', 'trimestre')):
        return None

    requisitos = db.query(Requisito).all()
    if not requisitos:
        return None

    ano_filtro = _extrair_ano(pergunta)

    if any(token in texto for token in ('por mês', 'por mes', 'mensal')):
        contagem: Counter[str] = Counter()
        for req in requisitos:
            criado = req.criado_em
            if isinstance(criado, str):
                try:
                    criado = datetime.fromisoformat(criado.replace('Z', '+00:00'))
                except ValueError:
                    criado = None
            if ano_filtro and criado and criado.year != ano_filtro:
                continue
            contagem[_mes_label(criado)] += 1
        linhas = [{'mes': mes, 'quantidade': qtd} for mes, qtd in sorted(contagem.items())]
        avisos_extra: list[str] = []
        if ano_filtro and not linhas:
            contagem_geral: Counter[str] = Counter()
            for req in requisitos:
                criado = req.criado_em
                if isinstance(criado, str):
                    try:
                        criado = datetime.fromisoformat(criado.replace('Z', '+00:00'))
                    except ValueError:
                        criado = None
                contagem_geral[_mes_label(criado)] += 1
            linhas = [{'mes': mes, 'quantidade': qtd} for mes, qtd in sorted(contagem_geral.items())]
            avisos_extra.append(f'Sem registros em {ano_filtro}; exibindo todos os meses disponíveis.')
        resposta = _resposta_local(
            pergunta=pergunta,
            correlation_id=correlation_id,
            metrica='contagem_por_mes',
            dimensoes=['mes'],
            colunas=['mes', 'quantidade'],
            linhas=linhas,
            sql='SELECT strftime("%Y-%m", criado_em) AS mes, COUNT(*) AS quantidade FROM requisitos GROUP BY mes',
            filtros={'ano': ano_filtro} if ano_filtro else {},
        )
        if avisos_extra:
            resposta['avisos'] = avisos_extra + resposta['avisos']
        return resposta

    if any(token in texto for token in ('situa', 'status', 'aprovad', 'reprovad')):
        contagem = Counter((req.status or 'sem_status').strip().lower() for req in requisitos)
        linhas = [{'status': status, 'quantidade': qtd} for status, qtd in sorted(contagem.items(), key=lambda x: -x[1])]
        return _resposta_local(
            pergunta=pergunta,
            correlation_id=correlation_id,
            metrica='contagem_por_status',
            dimensoes=['status'],
            colunas=['status', 'quantidade'],
            linhas=linhas,
            sql='SELECT status, COUNT(*) AS quantidade FROM requisitos GROUP BY status',
        )

    if any(token in texto for token in ('unidade', 'area', 'área')):
        contagem = Counter((req.area or 'sem_area').strip() for req in requisitos)
        linhas = [{'area': area, 'quantidade': qtd} for area, qtd in sorted(contagem.items(), key=lambda x: -x[1])]
        return _resposta_local(
            pergunta=pergunta,
            correlation_id=correlation_id,
            metrica='contagem_por_area',
            dimensoes=['area'],
            colunas=['area', 'quantidade'],
            linhas=linhas,
            sql='SELECT area, COUNT(*) AS quantidade FROM requisitos GROUP BY area',
        )

    if any(token in texto for token in ('total', 'quantas', 'quantos', 'contagem')):
        total = len(requisitos)
        linhas = [{'metrica': 'total_requisitos', 'valor': total}]
        return _resposta_local(
            pergunta=pergunta,
            correlation_id=correlation_id,
            metrica='total_requisitos',
            dimensoes=['geral'],
            colunas=['metrica', 'valor'],
            linhas=linhas,
            sql='SELECT COUNT(*) AS total_requisitos FROM requisitos',
        )

    return None
