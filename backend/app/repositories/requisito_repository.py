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

from collections.abc import Iterable

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.requisito import Requisito


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

    def criar(self, codigo: str, **campos) -> Requisito:
        requisito = Requisito(codigo=codigo, **campos)
        self._db.add(requisito)
        self._db.commit()
        self._db.refresh(requisito)
        return requisito
