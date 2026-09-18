#!/usr/bin/env python3
"""ReqSys — Movimento Email autocontido (#2861: Migrar rotina de e-mail para
Python — Prospecção Movimento / Portabilidade Consignado).

Pipeline completo (extração -> transformação -> renderização -> fila -> envio
SMTP) em um único arquivo, sem depender do backend do ReqSys (FastAPI /
SQLAlchemy) rodando — pensado para ser copiado sozinho para qualquer máquina
com Python 3.11+ e funcionar de forma autônoma (cron, Task Scheduler, Azure
Automation Runbook etc.).

Fonte funcional (equivalente ponto a ponto):
    backend/app/services/movimento_email/{models,transform,email_service,
    queue_repository,consumer,jobs,smtp_sender,repository}.py

Dependências: só stdlib, EXCETO `pyodbc` — importado só dentro do comando
"job", na hora de extrair do SQL Server de origem (não tem substituto stdlib
para falar com SQL Server). A fila durável usa `sqlite3` (stdlib) em vez de
SQLAlchemy/MongoDB — mesma porta, adapter mais leve, um arquivo `.sqlite3`
local. A renderização HTML usa `html.escape` + montagem de string pura, sem
Jinja2, para não exigir `pip install` de nada além de `pyodbc`.

GAP #2861-1 (ainda aberto — ver docs/architecture/movimento-email-pipeline.md
no monorepo): os 4 SELECTs abaixo assumem as views
`vw_prospeccao_movimento_*` criadas por
`backend/app/services/movimento_email/sql/views/V1__*.sql` (idempotentes via
`CREATE OR ALTER VIEW`, mas ainda um stub — 0 linhas — até a equipe de dados
confirmar o schema legado real do SSRS e substituir o corpo das views).

Uso:
    python movimento_email_autocontido.py job --data-referencia 2026-07-26 [--dry-run]
    python movimento_email_autocontido.py consumir [--dry-run] [--lote-max 20]
    python movimento_email_autocontido.py status

Configuração via variáveis de ambiente (nunca hardcode segredo — ADR-002):
    MOVIMENTO_EMAIL_SOURCE_DSN, MOVIMENTO_EMAIL_QUERY_TIMEOUT_SECONDS
    MOVIMENTO_EMAIL_SMTP_HOST/PORT/USER/PASSWORD/USE_TLS/FROM
    MOVIMENTO_EMAIL_RECIPIENTS (separados por vírgula)
    MOVIMENTO_EMAIL_QUEUE_DB_PATH (padrão: ./movimento_email_queue.sqlite3)
    MOVIMENTO_EMAIL_LOTE_MAX / _RESERVA_TIMEOUT_MINUTOS / _MAX_TENTATIVAS

`--dry-run` nunca produz um formato de saída igual ao de uma execução real
(chaves diferentes, sem "enviados"/"falhas") — para nunca parecer,
estruturalmente, um sucesso real.
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import smtplib
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger('movimento_email_autocontido')

T = TypeVar('T')

STATUS_PENDING = 'PENDING'
STATUS_PROCESSING = 'PROCESSING'
STATUS_SENT = 'SENT'
STATUS_ERROR = 'ERROR'


# ============================================================================
# Configuração (variáveis de ambiente)
# ============================================================================

def _env_bool(nome: str, default: str = 'false') -> bool:
    return (os.getenv(nome, default) or default).strip().lower() in {'1', 'true', 'yes', 'on'}


@dataclass(frozen=True)
class Config:
    source_dsn: str = field(default_factory=lambda: os.getenv('MOVIMENTO_EMAIL_SOURCE_DSN', '') or '')
    query_timeout_seconds: float = field(default_factory=lambda: float(os.getenv('MOVIMENTO_EMAIL_QUERY_TIMEOUT_SECONDS', '30') or '30'))
    smtp_host: str = field(default_factory=lambda: os.getenv('MOVIMENTO_EMAIL_SMTP_HOST', '') or '')
    smtp_port: int = field(default_factory=lambda: int(os.getenv('MOVIMENTO_EMAIL_SMTP_PORT', '587') or '587'))
    smtp_user: str = field(default_factory=lambda: os.getenv('MOVIMENTO_EMAIL_SMTP_USER', '') or '')
    smtp_password: str = field(default_factory=lambda: os.getenv('MOVIMENTO_EMAIL_SMTP_PASSWORD', '') or '')
    smtp_use_tls: bool = field(default_factory=lambda: _env_bool('MOVIMENTO_EMAIL_SMTP_USE_TLS', 'true'))
    smtp_from: str = field(default_factory=lambda: os.getenv('MOVIMENTO_EMAIL_SMTP_FROM', '') or '')
    recipients: str = field(default_factory=lambda: os.getenv('MOVIMENTO_EMAIL_RECIPIENTS', '') or '')
    queue_db_path: str = field(default_factory=lambda: os.getenv('MOVIMENTO_EMAIL_QUEUE_DB_PATH', 'movimento_email_queue.sqlite3') or 'movimento_email_queue.sqlite3')
    lote_max: int = field(default_factory=lambda: int(os.getenv('MOVIMENTO_EMAIL_LOTE_MAX', '20') or '20'))
    reserva_timeout_minutos: int = field(default_factory=lambda: int(os.getenv('MOVIMENTO_EMAIL_RESERVA_TIMEOUT_MINUTOS', '15') or '15'))
    max_tentativas: int = field(default_factory=lambda: int(os.getenv('MOVIMENTO_EMAIL_MAX_TENTATIVAS', '5') or '5'))

    @property
    def recipients_list(self) -> list[str]:
        return [e.strip() for e in self.recipients.split(',') if e.strip()]


# ============================================================================
# Domínio (dataclasses puras — ADR-001, sem I/O)
# ============================================================================

@dataclass(frozen=True)
class ItemFechamento:
    indicador: str
    valor: str
    observacao: str = ''


@dataclass(frozen=True)
class ItemPendenciaCadastro:
    protocolo: str
    cliente: str
    cpf: str
    pendencia: str
    dias_em_aberto: int
    responsavel: str = ''


@dataclass(frozen=True)
class ItemPendenciaHistorica:
    periodo_referencia: str
    pendencia: str
    quantidade: int
    percentual: float


@dataclass(frozen=True)
class ItemPendenciaObservacao:
    protocolo: str
    tipo_inconsistencia: str
    descricao: str
    etapa: str = ''


@dataclass(frozen=True)
class ContextoEmailMovimento:
    data_referencia: date
    correlation_id: str
    fechamento: list[ItemFechamento] = field(default_factory=list)
    pendencias_cadastro: list[ItemPendenciaCadastro] = field(default_factory=list)
    pendencias_historicas: list[ItemPendenciaHistorica] = field(default_factory=list)
    pendencias_observacao: list[ItemPendenciaObservacao] = field(default_factory=list)

    @property
    def total_pendencias(self) -> int:
        return len(self.pendencias_cadastro) + len(self.pendencias_historicas) + len(self.pendencias_observacao)


# ============================================================================
# Mascaramento de PII/segredo em log (ADR-002)
# ============================================================================

def mascarar_email(endereco: str | None) -> str:
    if not endereco or '@' not in endereco:
        return '[DADO_MASCARADO]'
    usuario, dominio = endereco.split('@', 1)
    inicial = usuario[0] if usuario else 'u'
    return f'{inicial}***@{dominio}'


def mascarar_segredo(_texto: str | None) -> str:
    return '[SEGREDO_REMOVIDO]'


_PADRAO_SENHA = re.compile(r'(senha|password|pwd)["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', re.IGNORECASE)


def _mascarar_erro(detalhe: str) -> str:
    return _PADRAO_SENHA.sub(r'\1=[SEGREDO_REMOVIDO]', detalhe)[:500]


# ============================================================================
# Retry + circuit breaker (ADR-010) — equivalente reduzido de app.core.resilience
# ============================================================================

class CircuitBreakerOpenError(RuntimeError):
    pass


@dataclass
class CircuitBreaker:
    nome: str
    limite_falhas: int = 3
    cooldown_segundos: int = 60
    falhas: int = field(default=0, init=False)
    aberto_em: datetime | None = field(default=None, init=False)

    def esta_aberto(self) -> bool:
        if self.aberto_em is None:
            return False
        return datetime.now(UTC) - self.aberto_em < timedelta(seconds=self.cooldown_segundos)

    def checar(self) -> None:
        if self.esta_aberto():
            raise CircuitBreakerOpenError(f'Circuito "{self.nome}" aberto após falhas consecutivas; aguardando cooldown.')

    def sucesso(self) -> None:
        self.falhas = 0
        self.aberto_em = None

    def falha(self) -> None:
        self.falhas += 1
        if self.falhas >= self.limite_falhas and self.aberto_em is None:
            self.aberto_em = datetime.now(UTC)
            logger.error('circuit_breaker_aberto circuito=%s falhas=%s', self.nome, self.falhas)


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    circuit: CircuitBreaker | None = None,
) -> T:
    if circuit is not None:
        circuit.checar()
    ultimo_erro: BaseException | None = None
    for tentativa in range(1, max_retries + 1):
        try:
            resultado = fn()
        except retry_on as exc:
            ultimo_erro = exc
            if tentativa < max_retries:
                time.sleep(backoff_seconds * (2 ** (tentativa - 1)))
            continue
        if circuit is not None:
            circuit.sucesso()
        return resultado
    if circuit is not None:
        circuit.falha()
    assert ultimo_erro is not None
    raise ultimo_erro


# ============================================================================
# Extração (SQL Server via pyodbc) — só usada pelo comando "job"
# ============================================================================

_SQL_FECHAMENTO = (
    'SELECT indicador, valor, observacao FROM vw_prospeccao_movimento_fechamento_diario '
    'WHERE data_referencia = ? ORDER BY indicador'
)
_SQL_PENDENCIAS_CADASTRO = (
    'SELECT protocolo, cliente, cpf, pendencia, dias_em_aberto, responsavel '
    'FROM vw_prospeccao_movimento_pendencias_cadastro WHERE data_referencia = ? ORDER BY dias_em_aberto DESC'
)
_SQL_PENDENCIAS_HISTORICAS = (
    'SELECT periodo_referencia, pendencia, quantidade, percentual '
    'FROM vw_prospeccao_movimento_pendencias_historicas WHERE data_referencia = ? ORDER BY periodo_referencia DESC'
)
_SQL_PENDENCIAS_OBSERVACAO = (
    'SELECT protocolo, tipo_inconsistencia, descricao, etapa '
    'FROM vw_prospeccao_movimento_pendencias_observacao WHERE data_referencia = ? ORDER BY tipo_inconsistencia'
)

_CIRCUITO_SQL = CircuitBreaker(nome='movimento_email_sql_source', limite_falhas=3, cooldown_segundos=60)


class ExtracaoError(RuntimeError):
    pass


def extrair_dados(cfg: Config, data_referencia: date) -> tuple[
    list[ItemFechamento], list[ItemPendenciaCadastro], list[ItemPendenciaHistorica], list[ItemPendenciaObservacao]
]:
    if not cfg.source_dsn:
        raise ExtracaoError('MOVIMENTO_EMAIL_SOURCE_DSN não configurado')

    import pyodbc

    def _consultar(sql: str) -> list[tuple]:
        def _rodar() -> list[tuple]:
            conexao = pyodbc.connect(cfg.source_dsn, timeout=cfg.query_timeout_seconds)
            try:
                conexao.timeout = cfg.query_timeout_seconds
                cursor = conexao.cursor()
                cursor.execute(sql, data_referencia)
                return cursor.fetchall()
            finally:
                conexao.close()

        try:
            return call_with_retry(_rodar, max_retries=3, backoff_seconds=1.0, retry_on=(pyodbc.Error,), circuit=_CIRCUITO_SQL)
        except pyodbc.Error as exc:
            raise ExtracaoError(f'Falha ao consultar origem SQL Server: {exc}') from exc

    fechamento = [
        ItemFechamento(indicador=str(linha[0]), valor=str(linha[1]), observacao=str(linha[2] or ''))
        for linha in _consultar(_SQL_FECHAMENTO)
    ]
    pendencias_cadastro = [
        ItemPendenciaCadastro(
            protocolo=str(linha[0]), cliente=str(linha[1]), cpf=str(linha[2]), pendencia=str(linha[3]),
            dias_em_aberto=int(linha[4] or 0), responsavel=str(linha[5] or ''),
        )
        for linha in _consultar(_SQL_PENDENCIAS_CADASTRO)
    ]
    pendencias_historicas = [
        ItemPendenciaHistorica(
            periodo_referencia=str(linha[0]), pendencia=str(linha[1]), quantidade=int(linha[2] or 0), percentual=float(linha[3] or 0.0),
        )
        for linha in _consultar(_SQL_PENDENCIAS_HISTORICAS)
    ]
    pendencias_observacao = [
        ItemPendenciaObservacao(protocolo=str(linha[0]), tipo_inconsistencia=str(linha[1]), descricao=str(linha[2]), etapa=str(linha[3] or ''))
        for linha in _consultar(_SQL_PENDENCIAS_OBSERVACAO)
    ]
    return fechamento, pendencias_cadastro, pendencias_historicas, pendencias_observacao


# ============================================================================
# Transformação (função pura)
# ============================================================================

def montar_contexto(
    *,
    data_referencia: date,
    correlation_id: str,
    fechamento: list[ItemFechamento],
    pendencias_cadastro: list[ItemPendenciaCadastro],
    pendencias_historicas: list[ItemPendenciaHistorica],
    pendencias_observacao: list[ItemPendenciaObservacao],
) -> ContextoEmailMovimento:
    return ContextoEmailMovimento(
        data_referencia=data_referencia,
        correlation_id=correlation_id,
        fechamento=list(fechamento),
        pendencias_cadastro=list(pendencias_cadastro),
        pendencias_historicas=list(pendencias_historicas),
        pendencias_observacao=list(pendencias_observacao),
    )


# ============================================================================
# Renderização (HTML + texto) — string building puro, sem Jinja2
# ============================================================================

def _linha_tabela(cor_fundo: str, celulas: Iterable[str]) -> str:
    tds = ''.join(f'<td style="padding:8px 10px;font-size:13px;border-top:1px solid #e5e7eb;">{c}</td>' for c in celulas)
    return f'<tr style="background:{cor_fundo};">{tds}</tr>'


def render_html(contexto: ContextoEmailMovimento) -> str:
    e = html.escape

    if contexto.fechamento:
        linhas = ''.join(
            _linha_tabela('#f8fafc' if i % 2 == 0 else '#ffffff', [e(it.indicador), f'<b>{e(it.valor)}</b>', e(it.observacao)])
            for i, it in enumerate(contexto.fechamento)
        )
        bloco_fechamento = (
            '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
            'style="border-collapse:collapse;border:1px solid #e5e7eb;">'
            '<tr style="background:#0f172a;color:#fff;">'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Indicador</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Valor</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Observação</td></tr>'
            f'{linhas}</table>'
        )
    else:
        bloco_fechamento = '<p style="font-size:13px;color:#6b7280;">Sem indicadores de fechamento para a data de referência.</p>'

    if contexto.pendencias_cadastro:
        linhas = ''.join(
            _linha_tabela(
                '#fffbeb' if i % 2 == 0 else '#ffffff',
                [e(it.protocolo), e(it.cliente), e(it.cpf), e(it.pendencia), f'<b>{it.dias_em_aberto}</b>', e(it.responsavel)],
            )
            for i, it in enumerate(contexto.pendencias_cadastro)
        )
        bloco_cadastro = (
            '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
            'style="border-collapse:collapse;border:1px solid #e5e7eb;">'
            '<tr style="background:#92400e;color:#fff;">'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Protocolo</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Cliente</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">CPF</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Pendência</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Dias em aberto</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Responsável</td></tr>'
            f'{linhas}</table>'
        )
    else:
        bloco_cadastro = '<p style="font-size:13px;color:#6b7280;">Sem pendências de cadastramento em aberto.</p>'

    if contexto.pendencias_historicas:
        linhas = ''.join(
            _linha_tabela(
                '#eff6ff' if i % 2 == 0 else '#ffffff',
                [e(it.periodo_referencia), e(it.pendencia), f'<b>{it.quantidade}</b>', f'{it.percentual:.1f}%'],
            )
            for i, it in enumerate(contexto.pendencias_historicas)
        )
        bloco_historico = (
            '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
            'style="border-collapse:collapse;border:1px solid #e5e7eb;">'
            '<tr style="background:#1e3a8a;color:#fff;">'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Período</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Pendência</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Quantidade</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">%</td></tr>'
            f'{linhas}</table>'
        )
    else:
        bloco_historico = '<p style="font-size:13px;color:#6b7280;">Sem histórico de pendências para o período.</p>'

    if contexto.pendencias_observacao:
        linhas = ''.join(
            _linha_tabela(
                '#fef2f2' if i % 2 == 0 else '#ffffff',
                [e(it.protocolo), e(it.tipo_inconsistencia), e(it.descricao), e(it.etapa)],
            )
            for i, it in enumerate(contexto.pendencias_observacao)
        )
        bloco_observacao = (
            '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
            'style="border-collapse:collapse;border:1px solid #e5e7eb;">'
            '<tr style="background:#991b1b;color:#fff;">'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Protocolo</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Tipo</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Descrição</td>'
            '<td style="padding:8px 10px;font-size:12px;font-weight:bold;">Etapa</td></tr>'
            f'{linhas}</table>'
        )
    else:
        bloco_observacao = '<p style="font-size:13px;color:#6b7280;">Sem inconsistências de observação/tratamento pendentes.</p>'

    return f'''<!doctype html>
<html lang="pt-BR"><body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;color:#111827;">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f4f6f9;border-collapse:collapse;"><tr><td align="center" style="padding:24px;">
<table role="presentation" cellpadding="0" cellspacing="0" width="900" style="max-width:900px;width:100%;background:#fff;border-collapse:collapse;border:1px solid #e5e7eb;">
<tr><td style="background:#0f172a;color:#fff;padding:24px;">
<h1 style="margin:0;font-size:22px;">Prospecção Movimento — Portabilidade Consignado</h1>
<p style="margin:8px 0 0 0;color:#cbd5e1;font-size:14px;">Resumo diário de {e(contexto.data_referencia.isoformat())}</p>
</td></tr>
<tr><td style="padding:20px;">
<h2 style="font-size:17px;margin:0 0 12px 0;">Fechamento diário</h2>{bloco_fechamento}
</td></tr>
<tr><td style="padding:0 20px 20px 20px;">
<h2 style="font-size:17px;margin:0 0 12px 0;">Pendências de cadastramento ({len(contexto.pendencias_cadastro)})</h2>{bloco_cadastro}
</td></tr>
<tr><td style="padding:0 20px 20px 20px;">
<h2 style="font-size:17px;margin:0 0 12px 0;">Pendências históricas</h2>{bloco_historico}
</td></tr>
<tr><td style="padding:0 20px 20px 20px;">
<h2 style="font-size:17px;margin:0 0 12px 0;">Pendências de observação/tratamento</h2>{bloco_observacao}
</td></tr>
<tr><td style="background:#111827;color:#cbd5e1;padding:14px;font-size:12px;">
ReqSys — Migração rotina de e-mail Prospecção Movimento (#2861) • Correlation ID: {e(contexto.correlation_id)}
</td></tr>
</table></td></tr></table></body></html>'''


def render_texto(contexto: ContextoEmailMovimento) -> str:
    linhas = [f'Prospecção Movimento — Portabilidade Consignado ({contexto.data_referencia.isoformat()})', '', 'FECHAMENTO DIÁRIO', '-' * 18]
    linhas.extend(
        (f'{it.indicador}: {it.valor} ({it.observacao})' for it in contexto.fechamento)
        if contexto.fechamento else ['Sem indicadores de fechamento para a data de referência.']
    )
    linhas.extend(['', f'PENDÊNCIAS DE CADASTRAMENTO ({len(contexto.pendencias_cadastro)})', '-' * 40])
    linhas.extend(
        (f'{it.protocolo} | {it.cliente} | {it.cpf} | {it.pendencia} | {it.dias_em_aberto} dias | {it.responsavel}' for it in contexto.pendencias_cadastro)
        if contexto.pendencias_cadastro else ['Sem pendências de cadastramento em aberto.']
    )
    linhas.extend(['', 'PENDÊNCIAS HISTÓRICAS', '-' * 22])
    linhas.extend(
        (f'{it.periodo_referencia} | {it.pendencia} | {it.quantidade} ({it.percentual:.1f}%)' for it in contexto.pendencias_historicas)
        if contexto.pendencias_historicas else ['Sem histórico de pendências para o período.']
    )
    linhas.extend(['', 'PENDÊNCIAS DE OBSERVAÇÃO/TRATAMENTO', '-' * 36])
    linhas.extend(
        (f'{it.protocolo} | {it.tipo_inconsistencia} | {it.descricao} | {it.etapa}' for it in contexto.pendencias_observacao)
        if contexto.pendencias_observacao else ['Sem inconsistências de observação/tratamento pendentes.']
    )
    linhas.extend(['', f'Correlation ID: {contexto.correlation_id}'])
    return '\n'.join(linhas)


def montar_mensagem_mime(contexto: ContextoEmailMovimento, *, remetente: str, destinatarios: list[str]) -> EmailMessage:
    mensagem = EmailMessage()
    mensagem['From'] = remetente
    mensagem['To'] = ', '.join(destinatarios)
    mensagem['Subject'] = f'Prospecção Movimento — Resumo diário {contexto.data_referencia.isoformat()}'
    mensagem['X-Correlation-ID'] = contexto.correlation_id
    mensagem['X-ReqSys-Report-Type'] = 'prospeccao-movimento-diario'
    mensagem.set_content(render_texto(contexto), subtype='plain', charset='utf-8')
    mensagem.add_alternative(render_html(contexto), subtype='html', charset='utf-8')
    return mensagem


# ============================================================================
# Fila durável (sqlite3 local) — mesma máquina de estados de queue_repository.py
# ============================================================================

def _conectar_fila(cfg: Config) -> sqlite3.Connection:
    conexao = sqlite3.connect(cfg.queue_db_path)
    conexao.execute('''
        CREATE TABLE IF NOT EXISTS movimento_email_dispatch (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_id TEXT NOT NULL,
            data_referencia TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            destinatarios TEXT NOT NULL DEFAULT '',
            assunto TEXT NOT NULL DEFAULT '',
            html_body TEXT NOT NULL DEFAULT '',
            text_body TEXT NOT NULL DEFAULT '',
            reserved_at TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 5,
            error_detail TEXT NOT NULL DEFAULT '',
            sent_at TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    conexao.commit()
    return conexao


def enfileirar(conexao: sqlite3.Connection, *, correlation_id: str, data_referencia: date, destinatarios: list[str],
               assunto: str, html_body: str, text_body: str, max_retries: int) -> int:
    cursor = conexao.execute(
        'INSERT INTO movimento_email_dispatch '
        '(correlation_id, data_referencia, status, destinatarios, assunto, html_body, text_body, max_retries, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (correlation_id, data_referencia.isoformat(), STATUS_PENDING, ', '.join(destinatarios), assunto, html_body,
         text_body, max_retries, datetime.now(UTC).isoformat()),
    )
    conexao.commit()
    item_id = cursor.lastrowid
    logger.info('movimento_email_enfileirado id=%s correlation_id=%s destinatarios=%s',
                item_id, correlation_id, ', '.join(mascarar_email(d) for d in destinatarios))
    return item_id


def limpar_reservas_travadas(conexao: sqlite3.Connection, *, timeout_minutos: int) -> int:
    """Devolve para PENDING itens travados em PROCESSING além do timeout —
    instrução global obrigatória para fluxos que reservam registros; roda
    sempre antes de reservar um novo lote e loga quando libera algo."""
    limite = (datetime.now(UTC) - timedelta(minutes=timeout_minutos)).isoformat()
    travados = conexao.execute(
        'SELECT id, correlation_id FROM movimento_email_dispatch WHERE status = ? AND reserved_at <= ?',
        (STATUS_PROCESSING, limite),
    ).fetchall()
    for item_id, correlation_id in travados:
        conexao.execute('UPDATE movimento_email_dispatch SET status = ?, reserved_at = NULL WHERE id = ?', (STATUS_PENDING, item_id))
        logger.info('movimento_email_reserva_travada_liberada id=%s correlation_id=%s', item_id, correlation_id)
    if travados:
        conexao.commit()
    return len(travados)


def reservar_lote(conexao: sqlite3.Connection, *, lote_max: int) -> list[sqlite3.Row]:
    conexao.row_factory = sqlite3.Row
    candidatos = conexao.execute(
        'SELECT id FROM movimento_email_dispatch WHERE status = ? ORDER BY created_at ASC LIMIT ?',
        (STATUS_PENDING, lote_max),
    ).fetchall()
    if not candidatos:
        return []

    agora = datetime.now(UTC).isoformat()
    ids = [item['id'] for item in candidatos]
    for item_id in ids:
        conexao.execute('UPDATE movimento_email_dispatch SET status = ?, reserved_at = ? WHERE id = ?', (STATUS_PROCESSING, agora, item_id))
    conexao.commit()

    # Re-busca após o commit — as Row acima refletem o estado ANTES do UPDATE
    # (sqlite3.Row é uma cópia estática do momento do fetch, não uma view viva).
    marcadores = ','.join('?' * len(ids))
    return conexao.execute(
        f'SELECT * FROM movimento_email_dispatch WHERE id IN ({marcadores}) ORDER BY created_at ASC',
        ids,
    ).fetchall()


def marcar_enviado(conexao: sqlite3.Connection, item_id: int) -> None:
    conexao.execute(
        "UPDATE movimento_email_dispatch SET status = ?, sent_at = ?, error_detail = '' WHERE id = ?",
        (STATUS_SENT, datetime.now(UTC).isoformat(), item_id),
    )
    conexao.commit()
    logger.info('movimento_email_enviado id=%s', item_id)


def marcar_erro(conexao: sqlite3.Connection, item: sqlite3.Row, detalhe: str) -> str:
    nova_tentativa = item['retry_count'] + 1
    novo_status = STATUS_ERROR if nova_tentativa >= item['max_retries'] else STATUS_PENDING
    conexao.execute(
        'UPDATE movimento_email_dispatch SET status = ?, retry_count = ?, error_detail = ?, reserved_at = NULL WHERE id = ?',
        (novo_status, nova_tentativa, detalhe[:2000], item['id']),
    )
    conexao.commit()
    logger.warning('movimento_email_falha id=%s tentativa=%s status=%s', item['id'], nova_tentativa, novo_status)
    return novo_status


def snapshot(conexao: sqlite3.Connection) -> dict[str, int]:
    contagens = {STATUS_PENDING: 0, STATUS_PROCESSING: 0, STATUS_SENT: 0, STATUS_ERROR: 0}
    for status, total in conexao.execute('SELECT status, COUNT(*) FROM movimento_email_dispatch GROUP BY status'):
        contagens[status] = total
    return contagens


def listar_recentes(conexao: sqlite3.Connection, *, limite: int = 20) -> list[dict[str, Any]]:
    """Últimos itens da fila (qualquer status), mais recentes primeiro — só
    metadados operacionais (nunca html_body/text_body/destinatarios completos,
    ADR-002) para alimentar o dashboard sem publicar dado sensível."""
    conexao.row_factory = sqlite3.Row
    linhas = conexao.execute(
        'SELECT id, correlation_id, assunto, status, retry_count, created_at, sent_at '
        'FROM movimento_email_dispatch ORDER BY created_at DESC LIMIT ?',
        (limite,),
    ).fetchall()
    return [dict(linha) for linha in linhas]


# ============================================================================
# Dashboard (HTML autocontido em ops-dashboard/movimento-email/) — ADR-007/ADR-009
# ============================================================================

def classificar_saude(contagens: dict[str, int]) -> str:
    if contagens.get(STATUS_ERROR, 0) > 0:
        return 'vermelho'
    if contagens.get(STATUS_PROCESSING, 0) > 0:
        return 'azul'
    if contagens.get(STATUS_PENDING, 0) or contagens.get(STATUS_SENT, 0):
        return 'verde'
    return 'cinza'


def construir_dashboard_data(contagens: dict[str, int], itens_recentes: list[dict[str, Any]]) -> dict[str, Any]:
    """Função pura (sem I/O) — monta o JSON consumido por
    ops-dashboard/movimento-email/index.html. Separada de `cmd_dashboard`
    (que só lê a fila e escreve o arquivo) para ser testável sem sqlite/disco."""
    return {
        'schema_version': '1.0.0',
        'component': 'movimento_email_dispatch',
        'contagens': {
            STATUS_PENDING: contagens.get(STATUS_PENDING, 0),
            STATUS_PROCESSING: contagens.get(STATUS_PROCESSING, 0),
            STATUS_SENT: contagens.get(STATUS_SENT, 0),
            STATUS_ERROR: contagens.get(STATUS_ERROR, 0),
        },
        'saude': classificar_saude(contagens),
        'itens_recentes': itens_recentes,
        'generated_at': datetime.now(UTC).isoformat(),
    }


# ============================================================================
# Envio SMTP (ADR-010: timeout + retry + circuit breaker)
# ============================================================================

_CIRCUITO_SMTP = CircuitBreaker(nome='movimento_email_smtp', limite_falhas=3, cooldown_segundos=60)


class EnvioEmailError(RuntimeError):
    pass


def enviar_smtp(cfg: Config, mensagem: EmailMessage) -> None:
    if not cfg.smtp_host:
        raise EnvioEmailError('MOVIMENTO_EMAIL_SMTP_HOST não configurado')

    def _enviar_uma_vez() -> None:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
            if cfg.smtp_use_tls:
                smtp.starttls()
            if cfg.smtp_user:
                smtp.login(cfg.smtp_user, cfg.smtp_password)
            smtp.send_message(mensagem)

    def _enviar_com_status() -> bool:
        _enviar_uma_vez()
        return True

    try:
        call_with_retry(_enviar_com_status, max_retries=3, backoff_seconds=1.0, retry_on=(smtplib.SMTPException, OSError), circuit=_CIRCUITO_SMTP)
    except (smtplib.SMTPException, OSError) as exc:
        erro_mascarado = _mascarar_erro(str(exc))
        logger.error('movimento_email_smtp_falhou erro=%s', erro_mascarado)
        raise EnvioEmailError(erro_mascarado) from exc


# ============================================================================
# Comandos CLI
# ============================================================================

def cmd_job(args: argparse.Namespace) -> int:
    cfg = Config()
    data_referencia = date.fromisoformat(args.data_referencia) if args.data_referencia else datetime.now(UTC).date()
    correlation_id = args.correlation_id or str(uuid.uuid4())
    destinatarios = args.destinatarios.split(',') if args.destinatarios else cfg.recipients_list
    destinatarios = [d.strip() for d in destinatarios if d.strip()]

    if not destinatarios:
        print('[ERRO] Nenhum destinatário configurado (MOVIMENTO_EMAIL_RECIPIENTS ou --destinatarios).')
        return 1

    try:
        fechamento, pend_cadastro, pend_historicas, pend_observacao = extrair_dados(cfg, data_referencia)
    except ExtracaoError as exc:
        print(f'[ERRO] Falha ao extrair dados de origem: {exc}')
        return 1

    contexto = montar_contexto(
        data_referencia=data_referencia, correlation_id=correlation_id,
        fechamento=fechamento, pendencias_cadastro=pend_cadastro,
        pendencias_historicas=pend_historicas, pendencias_observacao=pend_observacao,
    )
    assunto = f'Prospecção Movimento — Resumo diário {data_referencia.isoformat()}'
    html_body = render_html(contexto)
    text_body = render_texto(contexto)

    if args.dry_run:
        print({
            'dry_run': True,
            'seria_enfileirado': True,
            'correlation_id': correlation_id,
            'total_fechamento': len(fechamento),
            'total_pendencias': contexto.total_pendencias,
        })
        return 0

    conexao = _conectar_fila(cfg)
    try:
        item_id = enfileirar(
            conexao, correlation_id=correlation_id, data_referencia=data_referencia, destinatarios=destinatarios,
            assunto=assunto, html_body=html_body, text_body=text_body, max_retries=cfg.max_tentativas,
        )
    finally:
        conexao.close()

    print({'dry_run': False, 'dispatch_id': item_id, 'correlation_id': correlation_id,
           'total_fechamento': len(fechamento), 'total_pendencias': contexto.total_pendencias})
    return 0


def cmd_consumir(args: argparse.Namespace) -> int:
    cfg = Config()
    conexao = _conectar_fila(cfg)
    try:
        reservas_liberadas = limpar_reservas_travadas(conexao, timeout_minutos=cfg.reserva_timeout_minutos)

        if args.dry_run:
            conexao.row_factory = sqlite3.Row
            pendentes = conexao.execute(
                'SELECT * FROM movimento_email_dispatch WHERE status = ? ORDER BY created_at ASC LIMIT ?',
                (STATUS_PENDING, args.lote_max or cfg.lote_max),
            ).fetchall()
            print({
                'dry_run': True, 'enviado': False, 'reservas_liberadas': reservas_liberadas,
                'total_pendentes_no_lote': len(pendentes),
                'seriam_processados': [{'id': p['id'], 'correlation_id': p['correlation_id'], 'assunto': p['assunto']} for p in pendentes],
            })
            return 0

        if not cfg.smtp_host:
            print('[ERRO] MOVIMENTO_EMAIL_SMTP_HOST não configurado.')
            return 1

        lote = reservar_lote(conexao, lote_max=args.lote_max or cfg.lote_max)
        remetente = formataddr(('ReqSys', cfg.smtp_from)) if cfg.smtp_from else cfg.smtp_user

        enviados = 0
        falhas = 0
        itens_processados: list[dict[str, Any]] = []
        for item in lote:
            mensagem = EmailMessage()
            mensagem['From'] = remetente
            mensagem['To'] = item['destinatarios']
            mensagem['Subject'] = item['assunto']
            mensagem['X-Correlation-ID'] = item['correlation_id']
            mensagem.set_content(item['text_body'], subtype='plain', charset='utf-8')
            mensagem.add_alternative(item['html_body'], subtype='html', charset='utf-8')

            try:
                enviar_smtp(cfg, mensagem)
                marcar_enviado(conexao, item['id'])
                enviados += 1
                itens_processados.append({'id': item['id'], 'correlation_id': item['correlation_id'], 'status': STATUS_SENT})
            except EnvioEmailError as exc:
                novo_status = marcar_erro(conexao, item, str(exc))
                falhas += 1
                itens_processados.append({'id': item['id'], 'correlation_id': item['correlation_id'], 'status': novo_status})

        print({
            'dry_run': False, 'reservas_liberadas': reservas_liberadas, 'processados': len(lote),
            'enviados': enviados, 'falhas': falhas, 'itens': itens_processados,
        })
        return 0
    finally:
        conexao.close()


def cmd_status(_args: argparse.Namespace) -> int:
    cfg = Config()
    conexao = _conectar_fila(cfg)
    try:
        contagens = snapshot(conexao)
    finally:
        conexao.close()
    print({'contagens': contagens, 'saude': classificar_saude(contagens)})
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Gera data.json para ops-dashboard/movimento-email/index.html (ADR-007/
    ADR-012 — relatório autocontido, sem CDN externo, dado sensível nunca
    publicado: só metadados operacionais, nunca html_body/destinatarios)."""
    cfg = Config()
    conexao = _conectar_fila(cfg)
    try:
        contagens = snapshot(conexao)
        itens_recentes = listar_recentes(conexao, limite=args.limite)
    finally:
        conexao.close()

    dados = construir_dashboard_data(contagens, itens_recentes)
    destino = Path(args.output)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    print({'arquivo': str(destino), 'saude': dados['saude'], 'contagens': dados['contagens']})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='comando', required=True)

    p_job = sub.add_parser('job', help='Extrai, renderiza e enfileira o e-mail do dia.')
    p_job.add_argument('--data-referencia', default=None, help='AAAA-MM-DD (padrão: hoje, UTC).')
    p_job.add_argument('--correlation-id', default=None)
    p_job.add_argument('--destinatarios', default=None, help='Lista separada por vírgula (padrão: MOVIMENTO_EMAIL_RECIPIENTS).')
    p_job.add_argument('--dry-run', action='store_true')
    p_job.set_defaults(func=cmd_job)

    p_consumir = sub.add_parser('consumir', help='Processa um lote da fila (envia via SMTP).')
    p_consumir.add_argument('--lote-max', type=int, default=None)
    p_consumir.add_argument('--dry-run', action='store_true')
    p_consumir.set_defaults(func=cmd_consumir)

    p_status = sub.add_parser('status', help='Contagem por status na fila local.')
    p_status.set_defaults(func=cmd_status)

    p_dashboard = sub.add_parser('dashboard', help='Gera data.json para ops-dashboard/movimento-email/index.html.')
    p_dashboard.add_argument('--output', default='ops-dashboard/movimento-email/data.json')
    p_dashboard.add_argument('--limite', type=int, default=20, help='Máximo de itens recentes no dashboard.')
    p_dashboard.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
