"""Worker Python para Redmine — o elo que falta no fluxo PA-001-CreateRedmineIssue.

O Power Automate persiste em Dataverse (`cr85a_redminequeue`) porque o
conector HTTP genérico está bloqueado por DLP no tenant: chamar o Redmine
diretamente de dentro do flow não é uma opção. Este módulo é o lado ReqSys
dessa fila — lê os itens `PENDING` gravados pelo flow, cria a issue real no
Redmine (reaproveitando o adapter/circuit breaker de `github_redmine.py`) e
devolve o resultado para Dataverse (RedmineQueue + AgileSync + AuditLog),
fechando o loop que hoje termina em "⏳ Worker Python para Redmine".

Nomes de coluna assumidos (ver docs/architecture/redmine-sync-queue.md para a
lista completa e para o que ainda precisa ser confirmado/criado no ambiente
real): `cr85a_redminequeue` segue a mesma convenção `cr85a_<campo em
minúsculas>` já confirmada em `cr85a_agilesync` pelo próprio usuário
(CorrelationId -> cr85a_correlationid etc.). Use
`GET /v1/redmine-sync/diagnostico/coluna` para confirmar/corrigir ao vivo.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services import dataverse_queue_client as dv
from app.services.auditoria import registrar_evento
from app.services.dataverse_queue_client import DataverseError
from app.services.github_redmine import IntegracaoError, criar_issue_generica

logger = logging.getLogger('reqsys.redmine_sync_queue')

TABELA_REDMINE_QUEUE = 'cr85a_redminequeue'
TABELA_AGILESYNC = 'cr85a_agilesync'
TABELA_AUDITLOG = 'cr85a_auditlog'

STATUS_PENDING = 'PENDING'
STATUS_PROCESSING = 'PROCESSING'
STATUS_SENT = 'SENT'
STATUS_ERROR = 'ERROR'

AGILESYNC_STATUS_SYNCED = 'SYNCED'
AGILESYNC_STATUS_ERROR = 'ERROR'

DEFAULT_LOTE_MAX = 20
DEFAULT_RESERVA_TIMEOUT_MINUTOS = 15
DEFAULT_MAX_TENTATIVAS = 5

ATOR_WORKER = 'redmine_sync_worker'

_PADROES_SEGREDO = (
    re.compile(r'(X-Redmine-API-Key["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+', re.IGNORECASE),
    re.compile(r'(Bearer\s+)[A-Za-z0-9\-._~+/]+=*'),
)


def _mascarar(detalhe: str) -> str:
    """Remove possíveis segredos (API key do Redmine, tokens Bearer) antes de
    persistir o detalhe do erro em Dataverse/log (ADR-002)."""
    if not detalhe:
        return detalhe
    resultado = detalhe
    for padrao in _PADROES_SEGREDO:
        resultado = padrao.sub(r'\1[SEGREDO_REMOVIDO]', resultado)
    return resultado[:500]


async def diagnosticar_coluna(environment_url: str, tabela_logical_name: str, coluna_logical_name: str) -> dict[str, Any]:
    """Resolve ao vivo Data Type + Maximum Length de uma coluna do Dataverse —
    automatiza o diagnóstico manual pedido para `cr85a_agilesync.cr85a_correlationid`
    (erro "String or binary data would be truncated")."""
    return await dv.metadados_coluna(environment_url, tabela_logical_name, coluna_logical_name)


async def _registrar_auditlog_dataverse(environment_url: str, correlation_id: str, evento: str, sucesso: bool) -> None:
    """Best-effort: grava no MESMO `cr85a_auditlog` que o flow já usa, mantendo
    uma única trilha auditável ponta a ponta (Planner -> Redmine) por
    correlation_id (ADR-003). Uma falha aqui nunca deve derrubar o
    processamento real do item — o worker também audita localmente via
    `registrar_evento`."""
    try:
        entity_set = await dv.resolver_entity_set_name(environment_url, TABELA_AUDITLOG)
        await dv.create_row(environment_url, entity_set, {
            'cr85a_correlationid': correlation_id,
            'cr85a_evento': evento,
            'cr85a_origem': 'ReqSysRedmineSyncWorker',
            'cr85a_dataevento': datetime.now(UTC).isoformat(),
            'cr85a_sucesso': sucesso,
        })
    except DataverseError as exc:
        logger.warning('redmine_sync_auditlog_dataverse_falhou correlation_id=%s erro=%s', correlation_id, exc)


async def _atualizar_agilesync(environment_url: str, correlation_id: str, novo_status: str) -> None:
    if not correlation_id:
        return
    try:
        entity_set = await dv.resolver_entity_set_name(environment_url, TABELA_AGILESYNC)
        itens = await dv.list_rows(
            environment_url, entity_set,
            filtro=f"cr85a_correlationid eq '{correlation_id}'",
            select=['cr85a_agilesyncid'],
            top=1,
        )
        if not itens:
            logger.warning('redmine_sync_agilesync_nao_encontrado correlation_id=%s', correlation_id)
            return
        row_id = itens[0]['cr85a_agilesyncid']
        await dv.update_row(environment_url, entity_set, row_id, {'cr85a_plannerstatus': novo_status})
    except DataverseError as exc:
        logger.warning('redmine_sync_agilesync_update_falhou correlation_id=%s erro=%s', correlation_id, exc)


async def limpar_reservas_travadas(
    environment_url: str,
    *,
    timeout_minutos: int = DEFAULT_RESERVA_TIMEOUT_MINUTOS,
    db=None,
) -> int:
    """Devolve para `PENDING` itens travados em `PROCESSING` além do timeout —
    instrução global obrigatória para fluxos que reservam registros (ver
    CLAUDE.md do usuário). Roda sempre antes de reservar um novo lote."""
    entity_set = await dv.resolver_entity_set_name(environment_url, TABELA_REDMINE_QUEUE)
    limite = (datetime.now(UTC) - timedelta(minutes=timeout_minutos)).isoformat()
    itens = await dv.list_rows(
        environment_url, entity_set,
        filtro=f"cr85a_status eq '{STATUS_PROCESSING}' and cr85a_reservedat le {limite}",
        select=['cr85a_redminequeueid', 'cr85a_correlationid'],
        top=100,
    )
    for item in itens:
        row_id = item['cr85a_redminequeueid']
        correlation_id = item.get('cr85a_correlationid') or ''
        try:
            await dv.update_row(environment_url, entity_set, row_id, {'cr85a_status': STATUS_PENDING, 'cr85a_reservedat': None})
        except DataverseError as exc:
            logger.warning('redmine_sync_liberar_reserva_falhou row_id=%s erro=%s', row_id, exc)
            continue
        logger.info('redmine_sync_reserva_travada_liberada row_id=%s correlation_id=%s', row_id, correlation_id)
        if db is not None:
            registrar_evento(db, correlation_id, ATOR_WORKER, 'QUEUE_RESERVATION_TIMEOUT_RECOVERED', TABELA_REDMINE_QUEUE, row_id)
    return len(itens)


async def processar_fila_redmine(
    environment_url: str,
    *,
    lote_max: int = DEFAULT_LOTE_MAX,
    reserva_timeout_minutos: int = DEFAULT_RESERVA_TIMEOUT_MINUTOS,
    max_tentativas: int = DEFAULT_MAX_TENTATIVAS,
    dry_run: bool = False,
    db=None,
) -> dict[str, Any]:
    """Processa um lote da fila `cr85a_redminequeue`.

    `dry_run=True` retorna um formato deliberadamente diferente de um
    processamento real (`seriam_processados`, sem `criados`/`falhas`) — nunca
    chama o Redmine nem grava nada, para não correr o risco de um dry-run
    parecer estruturalmente igual a um sucesso real.
    """
    reservas_liberadas = await limpar_reservas_travadas(environment_url, timeout_minutos=reserva_timeout_minutos, db=db)
    entity_set_queue = await dv.resolver_entity_set_name(environment_url, TABELA_REDMINE_QUEUE)
    pendentes = await dv.list_rows(
        environment_url, entity_set_queue,
        filtro=f"cr85a_status eq '{STATUS_PENDING}'",
        top=lote_max,
        orderby='createdon asc',
    )

    if dry_run:
        return {
            'dry_run': True,
            'enviado': False,
            'reservas_liberadas': reservas_liberadas,
            'total_pendentes_no_lote': len(pendentes),
            'seriam_processados': [
                {
                    'row_id': item.get('cr85a_redminequeueid'),
                    'correlation_id': item.get('cr85a_correlationid'),
                    'subject': item.get('cr85a_subject'),
                }
                for item in pendentes
            ],
        }

    criados = 0
    falhas = 0
    itens_processados: list[dict[str, Any]] = []

    for item in pendentes:
        row_id = item.get('cr85a_redminequeueid')
        correlation_id = item.get('cr85a_correlationid') or ''
        subject = item.get('cr85a_subject') or ''
        tracker_id = item.get('cr85a_trackerid')
        tentativas_atuais = item.get('cr85a_retrycount') or 0

        try:
            await dv.update_row(environment_url, entity_set_queue, row_id, {
                'cr85a_status': STATUS_PROCESSING,
                'cr85a_reservedat': datetime.now(UTC).isoformat(),
            })
        except DataverseError as exc:
            logger.warning('redmine_sync_reserva_falhou row_id=%s erro=%s', row_id, exc)

        try:
            resultado = criar_issue_generica(subject=subject, tracker_id=tracker_id)
            await dv.update_row(environment_url, entity_set_queue, row_id, {'cr85a_status': STATUS_SENT})
            try:
                await dv.update_row(environment_url, entity_set_queue, row_id, {'cr85a_redmineissueid': resultado['issue_id']})
            except DataverseError:
                logger.info('redmine_sync_coluna_redmineissueid_ausente row_id=%s (opcional, ver docs)', row_id)

            await _atualizar_agilesync(environment_url, correlation_id, AGILESYNC_STATUS_SYNCED)
            await _registrar_auditlog_dataverse(environment_url, correlation_id, 'REDMINE_ISSUE_CREATED', True)
            if db is not None:
                registrar_evento(db, correlation_id, ATOR_WORKER, 'REDMINE_ISSUE_CREATED', TABELA_REDMINE_QUEUE, row_id)

            criados += 1
            itens_processados.append({
                'row_id': row_id, 'correlation_id': correlation_id, 'status': STATUS_SENT,
                'redmine_issue_id': resultado['issue_id'], 'redmine_url': resultado['redmine_url'],
            })

        except IntegracaoError as exc:
            erro_mascarado = _mascarar(str(exc))
            nova_tentativa = tentativas_atuais + 1
            novo_status = STATUS_ERROR if nova_tentativa >= max_tentativas else STATUS_PENDING
            try:
                await dv.update_row(environment_url, entity_set_queue, row_id, {
                    'cr85a_status': novo_status, 'cr85a_retrycount': nova_tentativa, 'cr85a_errordetail': erro_mascarado,
                })
            except DataverseError:
                await dv.update_row(environment_url, entity_set_queue, row_id, {'cr85a_status': novo_status})

            await _atualizar_agilesync(environment_url, correlation_id, AGILESYNC_STATUS_ERROR)
            await _registrar_auditlog_dataverse(environment_url, correlation_id, 'REDMINE_ISSUE_FAILED', False)
            if db is not None:
                registrar_evento(db, correlation_id, ATOR_WORKER, 'REDMINE_ISSUE_FAILED', TABELA_REDMINE_QUEUE, row_id)

            falhas += 1
            itens_processados.append({
                'row_id': row_id, 'correlation_id': correlation_id, 'status': novo_status,
                'tentativas': nova_tentativa, 'erro': erro_mascarado,
            })

    return {
        'dry_run': False,
        'reservas_liberadas': reservas_liberadas,
        'processados': len(pendentes),
        'criados': criados,
        'falhas': falhas,
        'itens': itens_processados,
    }
