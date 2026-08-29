import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.pentaho_integration_batch import PentahoIntegrationBatch
from app.schemas.pentaho_integration import PentahoLoteEntrada

logger = logging.getLogger(__name__)

STATUS_PENDENTE = 'PENDENTE'
STATUS_PROCESSANDO = 'PROCESSANDO'
STATUS_CONCLUIDO = 'CONCLUIDO'
STATUS_QUARENTENA = 'QUARENTENA'
VERSOES_SUPORTADAS = {1}


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _max_registros() -> int:
    valor = os.getenv('REQSYS_PENTAHO_MAX_REGISTROS', '10000')
    try:
        limite = int(valor)
    except ValueError as exc:
        raise RuntimeError('REQSYS_PENTAHO_MAX_REGISTROS deve ser inteiro') from exc
    if limite < 1:
        raise RuntimeError('REQSYS_PENTAHO_MAX_REGISTROS deve ser maior que zero')
    return limite


def validar_entrada(payload: PentahoLoteEntrada, idempotency_key: str, correlation_id: str) -> None:
    if payload.versaoEntrada not in VERSOES_SUPORTADAS:
        raise HTTPException(
            status_code=422,
            detail=f'Versão de entrada não suportada: {payload.versaoEntrada}. Suportadas: {sorted(VERSOES_SUPORTADAS)}',
        )
    if len(payload.registros) > _max_registros():
        raise HTTPException(status_code=413, detail='Quantidade de registros excede o limite configurado para um lote')
    if not idempotency_key.strip():
        raise HTTPException(status_code=422, detail='Idempotency-Key não pode ser vazio')
    if not correlation_id.strip():
        raise HTTPException(status_code=422, detail='X-Correlation-Id não pode ser vazio')


def criar_ou_obter_lote(
    db: Session,
    payload: PentahoLoteEntrada,
    idempotency_key: str,
    correlation_id: str,
) -> tuple[PentahoIntegrationBatch, bool]:
    validar_entrada(payload, idempotency_key, correlation_id)

    existente = (
        db.query(PentahoIntegrationBatch)
        .filter(PentahoIntegrationBatch.idempotency_key == idempotency_key)
        .first()
    )
    if existente is not None:
        return existente, True

    lote = PentahoIntegrationBatch(
        lote_id=str(uuid4()),
        lote_externo=payload.lote,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        origem=payload.origem,
        processo=payload.processo,
        versao_entrada=payload.versaoEntrada,
        data_referencia=payload.dataReferencia,
        payload_json=json.dumps(payload.model_dump(), ensure_ascii=False, separators=(',', ':')),
        status=STATUS_PENDENTE,
        registros_recebidos=len(payload.registros),
        registros_aceitos=0,
        registros_rejeitados=0,
        tentativas=0,
    )
    db.add(lote)
    try:
        db.commit()
        db.refresh(lote)
        return lote, False
    except IntegrityError:
        # Resolve corrida entre duas requisições com a mesma chave de idempotência.
        db.rollback()
        existente = (
            db.query(PentahoIntegrationBatch)
            .filter(PentahoIntegrationBatch.idempotency_key == idempotency_key)
            .first()
        )
        if existente is not None:
            return existente, True
        raise


def obter_lote(db: Session, lote_id: str) -> PentahoIntegrationBatch:
    lote = db.query(PentahoIntegrationBatch).filter(PentahoIntegrationBatch.lote_id == lote_id).first()
    if lote is None:
        raise HTTPException(status_code=404, detail='Lote Pentaho não encontrado')
    return lote


def serializar_status(lote: PentahoIntegrationBatch) -> dict:
    def iso(valor: datetime | None) -> str | None:
        return valor.isoformat() if valor else None

    return {
        'loteId': lote.lote_id,
        'lote': lote.lote_externo,
        'correlationId': lote.correlation_id,
        'processo': lote.processo,
        'versaoEntrada': lote.versao_entrada,
        'dataReferencia': lote.data_referencia,
        'status': lote.status,
        'registrosRecebidos': lote.registros_recebidos,
        'registrosAceitos': lote.registros_aceitos,
        'registrosRejeitados': lote.registros_rejeitados,
        'tentativas': lote.tentativas,
        'erroCodigo': lote.erro_codigo,
        'erroMensagem': lote.erro_mensagem,
        'criadoEm': iso(lote.criado_em),
        'atualizadoEm': iso(lote.atualizado_em),
        'processadoEm': iso(lote.processado_em),
    }


def _processar_lote(db: Session, lote: PentahoIntegrationBatch) -> None:
    lote.status = STATUS_PROCESSANDO
    lote.tentativas = (lote.tentativas or 0) + 1
    lote.erro_codigo = None
    lote.erro_mensagem = None
    db.add(lote)
    db.commit()

    try:
        payload = json.loads(lote.payload_json)
        registros = payload.get('registros')
        if not isinstance(registros, list):
            raise ValueError('Payload persistido sem lista de registros')

        # O adaptador valida e disponibiliza o lote. Regras de domínio permanecem
        # nos consumidores do ReqSys; aqui rejeitamos apenas registros vazios.
        aceitos = sum(1 for registro in registros if isinstance(registro, dict) and bool(registro))
        rejeitados = len(registros) - aceitos
        if aceitos == 0:
            raise ValueError('Nenhum registro válido foi recebido no lote')

        lote.registros_recebidos = len(registros)
        lote.registros_aceitos = aceitos
        lote.registros_rejeitados = rejeitados
        lote.status = STATUS_CONCLUIDO
        lote.processado_em = _agora()
        db.add(lote)
        db.commit()
    except Exception as exc:
        db.rollback()
        lote = db.query(PentahoIntegrationBatch).filter(PentahoIntegrationBatch.id == lote.id).first()
        if lote is None:
            raise
        lote.status = STATUS_QUARENTENA
        lote.erro_codigo = 'FALHA_PROCESSAMENTO_ADAPTADOR'
        lote.erro_mensagem = str(exc)[:2000]
        lote.processado_em = _agora()
        db.add(lote)
        db.commit()
        logger.exception(
            'Falha ao processar lote Pentaho',
            extra={'lote_id': lote.lote_id, 'correlation_id': lote.correlation_id},
        )


def processar_lote_assincrono(lote_id: str) -> None:
    db = SessionLocal()
    try:
        lote = db.query(PentahoIntegrationBatch).filter(PentahoIntegrationBatch.lote_id == lote_id).first()
        if lote is None:
            logger.error('Lote Pentaho não encontrado pelo consumidor', extra={'lote_id': lote_id})
            return
        if lote.status != STATUS_PENDENTE:
            return
        _processar_lote(db, lote)
    finally:
        db.close()


def preparar_reprocessamento(db: Session, lote_id: str) -> PentahoIntegrationBatch:
    lote = obter_lote(db, lote_id)
    if lote.status != STATUS_QUARENTENA:
        raise HTTPException(status_code=409, detail='Somente lotes em QUARENTENA podem ser reprocessados')
    lote.status = STATUS_PENDENTE
    lote.erro_codigo = None
    lote.erro_mensagem = None
    lote.processado_em = None
    db.add(lote)
    db.commit()
    db.refresh(lote)
    return lote


def obter_dashboard(db: Session, limite: int = 20) -> dict:
    hoje_utc = _agora().date().isoformat()
    lotes = db.query(PentahoIntegrationBatch).order_by(PentahoIntegrationBatch.criado_em.desc()).all()
    lotes_hoje = [lote for lote in lotes if lote.criado_em and lote.criado_em.date().isoformat() == hoje_utc]

    contagens = {
        'recebidos': len(lotes_hoje),
        'concluidos': sum(1 for lote in lotes_hoje if lote.status == STATUS_CONCLUIDO),
        'processando': sum(1 for lote in lotes_hoje if lote.status in {STATUS_PENDENTE, STATUS_PROCESSANDO}),
        'quarentena': sum(1 for lote in lotes_hoje if lote.status == STATUS_QUARENTENA),
    }

    processos: dict[str, dict] = {}
    for lote in lotes:
        if lote.processo not in processos:
            processos[lote.processo] = {
                'processo': lote.processo,
                'status': lote.status,
                'ultimaExecucao': lote.processado_em.isoformat() if lote.processado_em else None,
                'loteId': lote.lote_id,
            }

    return {
        'dataReferenciaUtc': hoje_utc,
        'contagens': contagens,
        'processos': list(processos.values()),
        'lotesRecentes': [serializar_status(lote) for lote in lotes[: max(1, min(limite, 100))]],
    }
