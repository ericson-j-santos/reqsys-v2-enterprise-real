"""Camada de extração (porta + adapter) da rotina de e-mail de Prospecção
Movimento (ADR-001, ADR-010).

`ProspeccaoMovimentoRepository` é a porta que `jobs.py` depende — casos de uso
não conhecem pyodbc nem a connection string de origem. O único adapter real
hoje é `SqlServerProspeccaoMovimentoRepository`; testes usam um dublê que
implementa o mesmo `Protocol` sem tocar rede/driver.

Os quatro SELECTs ficam em `sql/*.sql` como placeholders — os nomes reais das
views/tabelas de origem (que hoje alimentam o SSRS legado) ainda precisam ser
confirmados com a equipe de dados. Ver docs/architecture/movimento-email-pipeline.md
(gap #1) antes de apontar isto para produção.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Protocol

from app.core.resilience import CircuitBreaker, call_with_retry
from app.services.movimento_email.models import (
    ItemFechamento,
    ItemPendenciaCadastro,
    ItemPendenciaHistorica,
    ItemPendenciaObservacao,
)

logger = logging.getLogger('reqsys.movimento_email.repository')

_SQL_DIR = Path(__file__).resolve().parent / 'sql'

_CIRCUIT = CircuitBreaker(name='movimento_email_sql_source', failure_threshold=3, cooldown_seconds=60)


class ExtracaoError(RuntimeError):
    """Falha ao extrair dados de origem (SQL Server) para a rotina de e-mail."""


class ProspeccaoMovimentoRepository(Protocol):
    """Porta de extração dos 4 datasets consumidos pelo e-mail diário."""

    def get_fechamento(self, data_referencia: date) -> list[ItemFechamento]: ...

    def get_pendencias_cadastro(self, data_referencia: date) -> list[ItemPendenciaCadastro]: ...

    def get_pendencias_historicas(self, data_referencia: date) -> list[ItemPendenciaHistorica]: ...

    def get_pendencias_observacao(self, data_referencia: date) -> list[ItemPendenciaObservacao]: ...


def _carregar_sql(nome_arquivo: str) -> str:
    return (_SQL_DIR / nome_arquivo).read_text(encoding='utf-8')


_SQL_FECHAMENTO = _carregar_sql('fechamento_diario.sql')
_SQL_PENDENCIAS_CADASTRO = _carregar_sql('pendencias_cadastro.sql')
_SQL_PENDENCIAS_HISTORICAS = _carregar_sql('pendencias_historicas.sql')
_SQL_PENDENCIAS_OBSERVACAO = _carregar_sql('pendencias_observacao.sql')


class SqlServerProspeccaoMovimentoRepository:
    """Adapter real: extrai os 4 datasets do SQL Server corporativo via pyodbc.

    `dsn` é a connection string completa, resolvida via `get_secret` pelo
    chamador (nunca hardcoded — ADR-002). Timeout + retry + circuit breaker
    por chamada (ADR-010); import de `pyodbc` é local para não exigir driver
    ODBC instalado em ambientes que só rodam os testes.
    """

    def __init__(self, dsn: str, *, query_timeout_seconds: float = 30.0, max_retries: int = 3) -> None:
        if not dsn:
            raise ExtracaoError('DSN de origem (MOVIMENTO_EMAIL_SOURCE_DSN) não configurado')
        self._dsn = dsn
        self._query_timeout_seconds = query_timeout_seconds
        self._max_retries = max_retries

    def _executar(self, sql: str, data_referencia: date) -> list[tuple]:
        import pyodbc

        def _run() -> list[tuple]:
            conexao = pyodbc.connect(self._dsn, timeout=self._query_timeout_seconds)
            try:
                conexao.timeout = self._query_timeout_seconds
                cursor = conexao.cursor()
                cursor.execute(sql, data_referencia)
                return cursor.fetchall()
            finally:
                conexao.close()

        try:
            return call_with_retry(
                _run,
                max_retries=self._max_retries,
                backoff_seconds=1.0,
                retry_on=(pyodbc.Error,),
                circuit=_CIRCUIT,
            )
        except pyodbc.Error as exc:
            logger.error('movimento_email_extracao_falhou erro=%s', exc)
            raise ExtracaoError(f'Falha ao consultar origem SQL Server: {exc}') from exc

    def get_fechamento(self, data_referencia: date) -> list[ItemFechamento]:
        linhas = self._executar(_SQL_FECHAMENTO, data_referencia)
        return [
            ItemFechamento(indicador=str(linha[0]), valor=str(linha[1]), observacao=str(linha[2] or ''))
            for linha in linhas
        ]

    def get_pendencias_cadastro(self, data_referencia: date) -> list[ItemPendenciaCadastro]:
        linhas = self._executar(_SQL_PENDENCIAS_CADASTRO, data_referencia)
        return [
            ItemPendenciaCadastro(
                protocolo=str(linha[0]),
                cliente=str(linha[1]),
                cpf=str(linha[2]),
                pendencia=str(linha[3]),
                dias_em_aberto=int(linha[4] or 0),
                responsavel=str(linha[5] or ''),
            )
            for linha in linhas
        ]

    def get_pendencias_historicas(self, data_referencia: date) -> list[ItemPendenciaHistorica]:
        linhas = self._executar(_SQL_PENDENCIAS_HISTORICAS, data_referencia)
        return [
            ItemPendenciaHistorica(
                periodo_referencia=str(linha[0]),
                pendencia=str(linha[1]),
                quantidade=int(linha[2] or 0),
                percentual=float(linha[3] or 0.0),
            )
            for linha in linhas
        ]

    def get_pendencias_observacao(self, data_referencia: date) -> list[ItemPendenciaObservacao]:
        linhas = self._executar(_SQL_PENDENCIAS_OBSERVACAO, data_referencia)
        return [
            ItemPendenciaObservacao(
                protocolo=str(linha[0]),
                tipo_inconsistencia=str(linha[1]),
                descricao=str(linha[2]),
                etapa=str(linha[3] or ''),
            )
            for linha in linhas
        ]
