"""Porta de acesso a dados para Requisito (ADR-001).

Antes desta classe, `requisitos_metricas.py`, `requisitos_maturidade.py`,
`estatisticas.py`, `ai_quality.py`, `recomendacoes_ia.py`, `webhook_processor.py`
e `app/api/requisitos.py` escreviam `db.query(Requisito)...` cada um a sua
propria maneira, duplicando os mesmos padroes de consulta (contagem por status,
listagem ordenada, busca por codigo/id). Esta classe consolida esses padroes;
os services continuam recebendo `Session` diretamente (nao ha mudanca na
fronteira FastAPI/infra), mas delegam a leitura/escrita a este repositorio em
vez de montar a query eles mesmos.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.correlation import obter_correlation_id
from app.models.requisito import Requisito
from app.services.reqsys_orchestrator import (
    OrchestratorDemand,
    classificar_e_persistir_demanda,
)
from app.services.requisito_ml_runtime import avaliar_requisito_observacional

logger = logging.getLogger('reqsys.requisito_repository')


class RequisitoRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def contar_total(self) -> int:
        return self._db.query(Requisito).count()

    def contar_por_status_in(self, valores: Iterable[str]) -> int:
        return (
            self._db.query(Requisito)
            .filter(func.lower(Requisito.status).in_(valores))
            .count()
        )

    def contar_por_status_in_ou_contendo(self, valores: Iterable[str], contendo: str) -> int:
        """Como `contar_por_status_in`, mas tambem inclui status que contenham `contendo`
        (ex.: 'em_analise' e qualquer status com 'analise' no meio, como 'reanalise')."""
        return (
            self._db.query(Requisito)
            .filter(
                func.lower(Requisito.status).in_(valores)
                | func.lower(Requisito.status).like(f'%{contendo}%')
            )
            .count()
        )

    def contar_com_descricao_minima(self, tamanho_minimo: int) -> int:
        return (
            self._db.query(Requisito)
            .filter(func.length(func.coalesce(Requisito.descricao, '')) >= tamanho_minimo)
            .count()
        )

    def listar_todos(self, *, ordenar_por_id: str | None = None) -> list[Requisito]:
        """ordenar_por_id: None (ordem arbitraria do banco), 'asc' ou 'desc'."""
        query = self._db.query(Requisito)
        if ordenar_por_id == 'asc':
            query = query.order_by(Requisito.id)
        elif ordenar_por_id == 'desc':
            query = query.order_by(Requisito.id.desc())
        return query.all()

    def buscar_por_id(self, requisito_id: int) -> Requisito | None:
        return self._db.query(Requisito).filter(Requisito.id == requisito_id).first()

    def buscar_por_codigo(self, codigo: str) -> Requisito | None:
        return self._db.query(Requisito).filter(Requisito.codigo == codigo).first()

    def buscar_por_codigo_ou_id(self, identificador: str) -> Requisito | None:
        return (
            self._db.query(Requisito)
            .filter(
                or_(
                    Requisito.codigo == identificador,
                    Requisito.id == int(identificador) if identificador.isdigit() else False,
                )
            )
            .first()
        )

    def buscar_com_filtro_texto(self, termo: str | None, *, limit: int = 30) -> list[Requisito]:
        query = self._db.query(Requisito).order_by(Requisito.id.desc())
        if termo:
            padrao = f'%{termo.strip()}%'
            query = query.filter(
                or_(
                    Requisito.titulo.ilike(padrao),
                    Requisito.descricao.ilike(padrao),
                    Requisito.area.ilike(padrao),
                    Requisito.sistema.ilike(padrao),
                )
            )
        return query.limit(limit).all()

    def _iniciar_refinamento_automatico(self, requisito: Requisito) -> None:
        """Transforma `recebido` em estado transitório e roteia o item para refinamento.

        A transição de estado é persistida antes do roteamento. Assim, uma falha
        eventual do orquestrador não devolve o requisito ao limbo em `recebido`;
        o item permanece visível em `refinamento` e a falha de roteamento é
        registrada em log para remediação sem perda da demanda.
        """
        correlation_id = obter_correlation_id()

        requisito.status = 'refinamento'
        self._db.add(requisito)
        self._db.commit()
        self._db.refresh(requisito)

        try:
            rota = classificar_e_persistir_demanda(
                self._db,
                OrchestratorDemand(
                    titulo=requisito.titulo,
                    descricao=requisito.descricao or '',
                    origem='cadastro_requisito',
                    prioridade_informada=requisito.urgencia,
                    correlation_id=correlation_id,
                ),
            )
        except Exception:
            self._db.rollback()
            logger.exception(
                'requisito_refinamento_roteamento_falhou codigo=%s correlation_id=%s estado_preservado=refinamento',
                requisito.codigo,
                correlation_id or 'sem-correlation-id',
            )
            return

        logger.info(
            'requisito_refinamento_iniciado codigo=%s coordinator_id=%s routing_event_id=%s correlation_id=%s',
            requisito.codigo,
            rota['coordinator']['id'],
            rota.get('routing_event_id'),
            correlation_id or 'sem-correlation-id',
        )

    def criar(self, codigo: str, **campos) -> Requisito:
        status_informado_explicitamente = 'status' in campos
        requisito = Requisito(codigo=codigo, **campos)
        self._db.add(requisito)
        self._db.commit()
        self._db.refresh(requisito)

        # Entradas simples (UI e Power Automate) não informam status: nesses casos
        # `recebido` existe apenas como marco transitório e o refinamento começa
        # automaticamente. Fluxos governados que informam status explicitamente
        # mantêm a semântica já definida pelo chamador.
        if not status_informado_explicitamente:
            self._iniciar_refinamento_automatico(requisito)

        texto_observacional = '\n'.join(
            valor.strip()
            for valor in (requisito.titulo or '', requisito.descricao or '')
            if valor and valor.strip()
        )
        if texto_observacional:
            avaliar_requisito_observacional(
                texto_observacional,
                correlation_id=obter_correlation_id(),
            )

        return requisito
