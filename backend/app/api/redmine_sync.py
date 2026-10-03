"""API do worker Redmine Sync — fecha o loop do fluxo PA-001-CreateRedmineIssue
(Planner -> Dataverse -> Redmine), hoje sem alcance direto por causa da
política de DLP que bloqueia o conector HTTP genérico no Power Automate.
Ver docs/architecture/redmine-sync-queue.md.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.core.service_tokens import require_admin_or_service_token
from app.db import get_db
from app.schemas.redmine_sync import RedmineSyncProcessarRequest
from app.services import dataverse_queue_client as dv
from app.services.dataverse_queue_client import DataverseError
from app.services.redmine_sync_queue import (
    STATUS_ERROR,
    STATUS_PENDING,
    STATUS_PROCESSING,
    STATUS_SENT,
    TABELA_REDMINE_QUEUE,
    diagnosticar_coluna,
    processar_fila_redmine,
)

logger = logging.getLogger('reqsys.redmine_sync_api')

router = APIRouter(prefix='/v1/redmine-sync', tags=['Redmine Sync Queue'])

# Instancia unica (nao recriada por request) para permitir override em testes
# via app.dependency_overrides — mesmo padrao de teams_gateway.py.
require_processar_auth = require_admin_or_service_token('redmine_sync:processar')


def _environment_url_configurado() -> str:
    url = (settings.redmine_sync_dataverse_url or '').strip()
    if not url:
        raise HTTPException(status_code=409, detail='REDMINE_SYNC_DATAVERSE_URL não configurado')
    return url


def _classificar_saude(contagens: dict[str, int]) -> str:
    if contagens.get(STATUS_ERROR, 0) > 0:
        return 'vermelho'
    if contagens.get(STATUS_PROCESSING, 0) > 0:
        return 'azul'
    return 'verde'


@router.get('/status', dependencies=[Depends(require_admin)])
async def redmine_sync_status():
    """Contagem por status na fila `cr85a_redminequeue` (estados ADR-007:
    verde=saudável, azul=em execução, vermelho=falha crítica)."""
    environment_url = _environment_url_configurado()
    try:
        entity_set = await dv.resolver_entity_set_name(environment_url, TABELA_REDMINE_QUEUE)
        contagens: dict[str, int] = {}
        for status in (STATUS_PENDING, STATUS_PROCESSING, STATUS_SENT, STATUS_ERROR):
            itens = await dv.list_rows(
                environment_url, entity_set,
                filtro=f"cr85a_status eq '{status}'",
                select=['cr85a_redminequeueid'],
                top=500,
            )
            contagens[status] = len(itens)
    except DataverseError as exc:
        raise HTTPException(status_code=502, detail=f'Falha ao consultar Dataverse: {exc}') from None
    return ok({'contagens': contagens, 'saude': _classificar_saude(contagens)})


@router.post('/processar')
async def redmine_sync_processar(
    payload: RedmineSyncProcessarRequest = RedmineSyncProcessarRequest(),
    ctx=Depends(require_processar_auth),
    db: Session = Depends(get_db),
):
    """Processa um lote da fila: libera reservas travadas (timeout
    configurável via REDMINE_SYNC_RESERVA_TIMEOUT_MINUTOS, padrão 15min — ver
    CLAUDE.md do usuário), cria issues reais no Redmine para os itens PENDING
    e grava o resultado de volta em RedmineQueue + AgileSync + AuditLog.

    `dry_run=true` mostra o que SERIA processado sem chamar o Redmine nem
    gravar nada (formato de resposta deliberadamente distinto de um
    processamento real).

    Autenticação: JWT admin (humano) OU `X-Service-Token` escopado para
    `redmine_sync:processar` (para acionar via cron/automação externa).
    """
    environment_url = _environment_url_configurado()
    correlation_id = resolver_correlation_id()
    try:
        resultado = await processar_fila_redmine(
            environment_url,
            lote_max=payload.lote_max or settings.redmine_sync_lote_max,
            reserva_timeout_minutos=settings.redmine_sync_reserva_timeout_minutos,
            max_tentativas=settings.redmine_sync_max_tentativas,
            dry_run=payload.dry_run,
            db=db,
        )
    except DataverseError as exc:
        raise HTTPException(status_code=502, detail=f'Falha ao acessar Dataverse: {exc}') from None
    return ok(resultado, correlation_id)


@router.get('/diagnostico/coluna', dependencies=[Depends(require_admin)])
async def redmine_sync_diagnostico_coluna(
    tabela: str = Query(default='cr85a_agilesync'),
    coluna: str = Query(default='cr85a_correlationid'),
):
    """Consulta ao vivo Data Type + Maximum Length de uma coluna do Dataverse —
    automatiza o diagnóstico do erro "String or binary data would be
    truncated" em `cr85a_agilesync.cr85a_correlationid` sem precisar abrir o
    Maker Portal manualmente.
    """
    environment_url = _environment_url_configurado()
    try:
        info = await diagnosticar_coluna(environment_url, tabela, coluna)
    except DataverseError as exc:
        raise HTTPException(status_code=502, detail=f'Falha ao consultar metadados do Dataverse: {exc}') from None

    alerta = None
    max_length = info.get('max_length')
    if coluna == 'cr85a_correlationid' and max_length is not None and max_length < 36:
        alerta = (
            f"MaxLength atual é {max_length}, mas um GUID (guid()) sempre tem 36 caracteres. "
            "Aumente a coluna para pelo menos 36 (recomendado 100) no Maker Portal — "
            "esse é o bloqueador confirmado."
        )
    return ok({**info, 'alerta': alerta})
