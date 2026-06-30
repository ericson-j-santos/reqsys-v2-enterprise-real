from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, or_
from sqlalchemy.orm import Session, joinedload

from app.models.requisito import (
    RecommendationIA,
    RecommendationIADecision,
    RecommendationIAOutcome,
    Requisito,
)

_URGENCIA_SCORE = {
    'critica': 0.95,
    'alta': 0.8,
    'media': 0.55,
    'baixa': 0.35,
}


def _score_por_urgencia(urgencia: str | None) -> float:
    return _URGENCIA_SCORE.get(str(urgencia or 'media').lower(), 0.55)


def serializar_incidente(requisito: Requisito) -> dict:
    descricao = (requisito.descricao or '').strip()
    resumo = descricao[:280] + ('…' if len(descricao) > 280 else '')
    return {
        'id': requisito.id,
        'titulo': requisito.titulo,
        'resumo_contexto': resumo or requisito.titulo,
        'modulo': requisito.area,
        'funcionalidade': requisito.sistema,
        'severidade': requisito.urgencia,
        'score_atual': _score_por_urgencia(requisito.urgencia),
    }


def listar_incidentes(db: Session, *, limit: int = 30, search: str | None = None) -> list[dict]:
    query = db.query(Requisito).order_by(desc(Requisito.id))
    if search:
        termo = f'%{search.strip()}%'
        query = query.filter(
            or_(
                Requisito.titulo.ilike(termo),
                Requisito.descricao.ilike(termo),
                Requisito.area.ilike(termo),
                Requisito.sistema.ilike(termo),
            )
        )
    return [serializar_incidente(item) for item in query.limit(limit).all()]


def obter_incidente(db: Session, incidente_id: int) -> dict | None:
    requisito = db.query(Requisito).filter(Requisito.id == incidente_id).first()
    return serializar_incidente(requisito) if requisito else None


def _serializar_decisao(decisao: RecommendationIADecision | None) -> dict | None:
    if not decisao:
        return None
    return {
        'aceita': decisao.aceita,
        'motivo_decisao': decisao.motivo_decisao,
        'decidido_por': decisao.decidido_por,
        'decidido_em': decisao.decidido_em.isoformat() if hasattr(decisao.decidido_em, 'isoformat') else str(decisao.decidido_em),
    }


def _serializar_outcome(outcome: RecommendationIAOutcome | None) -> dict | None:
    if not outcome:
        return None
    return {
        'foi_aplicada': outcome.foi_aplicada,
        'versao_aplicada': outcome.versao_aplicada,
        'outcome_positivo': outcome.outcome_positivo,
        'score_pos_correcao': outcome.score_pos_correcao,
        'observacao': outcome.observacao,
        'avaliado_em': outcome.avaliado_em.isoformat() if hasattr(outcome.avaliado_em, 'isoformat') else str(outcome.avaliado_em),
    }


def serializar_recomendacao(recomendacao: RecommendationIA) -> dict:
    return {
        'id': recomendacao.id,
        'id_incidente': recomendacao.requisito_id,
        'titulo': recomendacao.titulo,
        'contexto_incidente': recomendacao.contexto_incidente,
        'tipo_recomendacao': recomendacao.tipo_recomendacao,
        'confianca_ia': recomendacao.confianca_ia,
        'recomendacao': recomendacao.recomendacao,
        'modelo': recomendacao.modelo,
        'score_inicial': recomendacao.score_inicial,
        'criado_em': recomendacao.criado_em.isoformat() if hasattr(recomendacao.criado_em, 'isoformat') else str(recomendacao.criado_em),
        'decisao': _serializar_decisao(recomendacao.decisao),
        'outcome': _serializar_outcome(recomendacao.outcome),
    }


def listar_recomendacoes(db: Session, *, limit: int = 20) -> list[dict]:
    itens = (
        db.query(RecommendationIA)
        .options(joinedload(RecommendationIA.decisao), joinedload(RecommendationIA.outcome))
        .order_by(desc(RecommendationIA.id))
        .limit(limit)
        .all()
    )
    return [serializar_recomendacao(item) for item in itens]


def obter_recomendacao(db: Session, recomendacao_id: int) -> dict | None:
    item = (
        db.query(RecommendationIA)
        .options(joinedload(RecommendationIA.decisao), joinedload(RecommendationIA.outcome))
        .filter(RecommendationIA.id == recomendacao_id)
        .first()
    )
    return serializar_recomendacao(item) if item else None


def criar_recomendacao(db: Session, payload: dict) -> dict:
    requisito = db.query(Requisito).filter(Requisito.id == payload['id_incidente']).first()
    if not requisito:
        raise ValueError('Requisito/incidente não encontrado.')

    recomendacao = RecommendationIA(
        requisito_id=requisito.id,
        titulo=payload['titulo'],
        contexto_incidente=payload.get('contexto_incidente'),
        tipo_recomendacao=payload['tipo_recomendacao'],
        confianca_ia=float(payload.get('confianca_ia', 0.8)),
        recomendacao=payload['recomendacao'],
        modelo=payload.get('modelo'),
        score_inicial=payload.get('score_inicial'),
    )
    db.add(recomendacao)
    db.commit()
    db.refresh(recomendacao)
    return serializar_recomendacao(recomendacao)


def registrar_decisao(db: Session, recomendacao_id: int, payload: dict) -> dict:
    recomendacao = db.query(RecommendationIA).filter(RecommendationIA.id == recomendacao_id).first()
    if not recomendacao:
        raise ValueError('Recomendação não encontrada.')
    if recomendacao.decisao:
        raise ValueError('Decisão já registrada para esta recomendação.')

    decisao = RecommendationIADecision(
        recomendacao_id=recomendacao.id,
        aceita=bool(payload['aceita']),
        motivo_decisao=payload.get('motivo_decisao'),
        decidido_por=payload.get('decidido_por'),
    )
    db.add(decisao)
    db.commit()
    db.refresh(recomendacao)
    return obter_recomendacao(db, recomendacao_id) or {}


def registrar_outcome(db: Session, recomendacao_id: int, payload: dict) -> dict:
    recomendacao = db.query(RecommendationIA).filter(RecommendationIA.id == recomendacao_id).first()
    if not recomendacao:
        raise ValueError('Recomendação não encontrada.')
    if recomendacao.outcome:
        raise ValueError('Outcome já registrado para esta recomendação.')

    outcome = RecommendationIAOutcome(
        recomendacao_id=recomendacao.id,
        foi_aplicada=bool(payload['foi_aplicada']),
        versao_aplicada=payload.get('versao_aplicada'),
        outcome_positivo=payload.get('outcome_positivo'),
        score_pos_correcao=payload.get('score_pos_correcao'),
        observacao=payload.get('observacao'),
    )
    db.add(outcome)
    db.commit()
    return obter_recomendacao(db, recomendacao_id) or {}


def _filtrar_por_janela(query, campo, janela_dias: int):
    if janela_dias <= 0:
        return query
    limite = datetime.now(UTC) - timedelta(days=janela_dias)
    return query.filter(campo >= limite)


def calcular_dashboard_ia(db: Session, *, janela_dias: int = 30) -> dict:
    base_query = db.query(RecommendationIA)
    recomendacoes = _filtrar_por_janela(base_query, RecommendationIA.criado_em, janela_dias).all()
    recomendacao_ids = [item.id for item in recomendacoes]

    decisoes = []
    outcomes = []
    if recomendacao_ids:
        decisoes = db.query(RecommendationIADecision).filter(
            RecommendationIADecision.recomendacao_id.in_(recomendacao_ids)
        ).all()
        outcomes = db.query(RecommendationIAOutcome).filter(
            RecommendationIAOutcome.recomendacao_id.in_(recomendacao_ids)
        ).all()

    total_decisoes = len(decisoes)
    aceitas = sum(1 for item in decisoes if item.aceita)
    taxa_aceitacao = round(aceitas / total_decisoes, 4) if total_decisoes else 0.0

    aplicadas = [item for item in outcomes if item.foi_aplicada]
    positivas = [item for item in aplicadas if item.outcome_positivo is True]
    taxa_eficacia = round(len(positivas) / len(aplicadas), 4) if aplicadas else 0.0

    erros = []
    for decisao in decisoes:
        recomendacao = next((item for item in recomendacoes if item.id == decisao.recomendacao_id), None)
        if not recomendacao:
            continue
        previsto = float(recomendacao.confianca_ia or 0.5)
        observado = 1.0 if decisao.aceita else 0.0
        erros.append((previsto - observado) ** 2)
    brier_score = round(sum(erros) / len(erros), 4) if erros else 0.0

    return {
        'amostras_total': len(recomendacoes),
        'janela_dias': janela_dias,
        'metricas': {
            'taxa_aceitacao': {
                'valor': {
                    'taxa': taxa_aceitacao,
                    'aceitas': aceitas,
                    'total': total_decisoes,
                }
            },
            'eficacia_pos_correcao': {
                'valor': {
                    'taxa': taxa_eficacia,
                    'positivas': len(positivas),
                    'aplicadas': len(aplicadas),
                }
            },
            'calibracao': {
                'valor': {
                    'brier_score': brier_score,
                }
            },
        },
    }


def gerar_texto_recomendacao(
    *,
    titulo: str,
    contexto_incidente: str,
    tipo_recomendacao: str,
) -> dict:
    tipo = tipo_recomendacao or 'hotfix'
    contexto = (contexto_incidente or titulo or '').strip()
    templates = {
        'hotfix': (
            f'Aplicar hotfix focado em "{titulo}" com validação regressiva imediata e rollback documentado. '
            f'Contexto: {contexto[:220]}'
        ),
        'proxima_versao': (
            f'Planejar correção estrutural de "{titulo}" na próxima versão, com testes de regressão e evidência em PR. '
            f'Contexto: {contexto[:220]}'
        ),
        'backlog': (
            f'Priorizar item no backlog operacional para "{titulo}" com critérios de aceite e owner definido. '
            f'Contexto: {contexto[:220]}'
        ),
        'monitorar': (
            f'Manter monitoramento ativo de "{titulo}" com alertas e revisão em janela de observação. '
            f'Contexto: {contexto[:220]}'
        ),
    }
    texto = templates.get(tipo, templates['hotfix'])
    return {
        'recomendacao': texto,
        'confianca_ia': 0.72,
        'modelo': 'reqsys-heuristica-local',
    }
