import json
import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, update
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


def _inteiro_configurado(nome: str, padrao: int, minimo: int = 1) -> int:
    valor = os.getenv(nome, str(padrao))
    try:
        numero = int(valor)
    except ValueError as exc:
        raise RuntimeError(f'{nome} deve ser inteiro') from exc
    if numero < minimo:
        raise RuntimeError(f'{nome} deve ser maior ou igual a {minimo}')
    return numero


def _max_registros() -> int:
    return _inteiro_configurado('REQSYS_PENTAHO_MAX_REGISTROS', 10000)


def _timeout_processamento_segundos() -> int:
    return _inteiro_configurado('REQSYS_PENTAHO_PROCESSING_TIMEOUT_SECONDS', 300, minimo=10)


def _max_tentativas() -> int:
    return _inteiro_configurado('REQSYS_PENTAHO_MAX_TENTATIVAS', 5)


def _serializar_payload(payload: PentahoLoteEntrada) -> str:
    return json.dumps(
        payload.model_dump(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )


def _validar_reuso_idempotencia(existente: PentahoIntegrationBatch, payload_json: str) -> None:
    try:
        payload_existente = json.dumps(
            json.loads(existente.payload_json),
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=409,
            detail='Lote existente possui conteúdo inválido para validação de idempotência',
        ) from exc

    if payload_existente != payload_json:
        raise HTTPException(
            status_code=409,
            detail='Idempotency-Key já utilizada com conteúdo diferente',
        )


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


def _buscar_lote_por_idempotencia(db: Session, idempotency_key: str) -> PentahoIntegrationBatch | None:
    return (
        db.query(PentahoIntegrationBatch)
        .filter(PentahoIntegrationBatch.idempotency_key == idempotency_key)
        .first()
    )


def criar_ou_obter_lote(
    db: Session,
    payload: PentahoLoteEntrada,
    idempotency_key: str,
    correlation_id: str,
) -> tuple[PentahoIntegrationBatch, bool]:
    validar_entrada(payload, idempotency_key, correlation_id)
    payload_json = _serializar_payload(payload)

    existente = _buscar_lote_por_idempotencia(db, idempotency_key)
    if existente is not None:
        _validar_reuso_idempotencia(existente, payload_json)
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
        payload_json=payload_json,
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
        existente = _buscar_lote_por_idempotencia(db, idempotency_key)
        if existente is not None:
            _validar_reuso_idempotencia(existente, payload_json)
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


def reivindicar_lote(db: Session, lote_id: str) -> PentahoIntegrationBatch | None:
    """Move PENDENTE -> PROCESSANDO de forma atômica.

    O UPDATE condicionado ao estado garante que API e consumidor independente
    possam disputar o mesmo lote sem executar o trabalho duas vezes.
    """
    agora = _agora()
    resultado = db.execute(
        update(PentahoIntegrationBatch)
        .where(
            PentahoIntegrationBatch.lote_id == lote_id,
            PentahoIntegrationBatch.status == STATUS_PENDENTE,
        )
        .values(
            status=STATUS_PROCESSANDO,
            tentativas=func.coalesce(PentahoIntegrationBatch.tentativas, 0) + 1,
            atualizado_em=agora,
        )
    )
    db.commit()
    if resultado.rowcount != 1:
        return None
    return db.query(PentahoIntegrationBatch).filter(PentahoIntegrationBatch.lote_id == lote_id).first()


def _executar_lote_reivindicado(db: Session, lote: PentahoIntegrationBatch) -> None:
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
        lote.erro_codigo = None
        lote.erro_mensagem = None
        lote.atualizado_em = _agora()
        lote.processado_em = lote.atualizado_em
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
        lote.atualizado_em = _agora()
        lote.processado_em = lote.atualizado_em
        db.add(lote)
        db.commit()
        logger.exception(
            'Falha ao processar lote Pentaho',
            extra={'lote_id': lote.lote_id, 'correlation_id': lote.correlation_id},
        )


def processar_lote_por_id(db: Session, lote_id: str) -> bool:
    lote = reivindicar_lote(db, lote_id)
    if lote is None:
        return False
    _executar_lote_reivindicado(db, lote)
    return True


def processar_lote_assincrono(lote_id: str) -> None:
    """Atalho imediato da API; usa a mesma reivindicação do consumidor durável."""
    db = SessionLocal()
    try:
        processar_lote_por_id(db, lote_id)
    finally:
        db.close()


def processar_proximo_lote(db: Session, limite_busca: int = 20) -> str | None:
    candidatos = (
        db.query(PentahoIntegrationBatch.lote_id)
        .filter(PentahoIntegrationBatch.status == STATUS_PENDENTE)
        .order_by(PentahoIntegrationBatch.criado_em.asc(), PentahoIntegrationBatch.id.asc())
        .limit(max(1, min(limite_busca, 100)))
        .all()
    )
    for (lote_id,) in candidatos:
        if processar_lote_por_id(db, lote_id):
            return lote_id
    return None


def recuperar_lotes_abandonados(
    db: Session,
    *,
    agora: datetime | None = None,
    timeout_segundos: int | None = None,
    max_tentativas: int | None = None,
) -> dict[str, int]:
    """Recupera PROCESSANDO sem atualização dentro da janela de segurança.

    Até o limite de tentativas o lote volta para PENDENTE. Ao atingir o limite,
    ele é encerrado em QUARENTENA para evitar repetição infinita após falhas de
    processo ou reinicializações sucessivas.
    """
    instante = agora or _agora()
    timeout = timeout_segundos if timeout_segundos is not None else _timeout_processamento_segundos()
    limite_tentativas = max_tentativas if max_tentativas is not None else _max_tentativas()
    if timeout < 1:
        raise ValueError('timeout_segundos deve ser maior que zero')
    if limite_tentativas < 1:
        raise ValueError('max_tentativas deve ser maior que zero')

    limite = instante - timedelta(seconds=timeout)
    condicao_abandono = or_(
        PentahoIntegrationBatch.atualizado_em < limite,
        and_(
            PentahoIntegrationBatch.atualizado_em.is_(None),
            PentahoIntegrationBatch.criado_em < limite,
        ),
    )
    abandonados = (
        db.query(PentahoIntegrationBatch)
        .filter(
            PentahoIntegrationBatch.status == STATUS_PROCESSANDO,
            condicao_abandono,
        )
        .order_by(PentahoIntegrationBatch.id.asc())
        .all()
    )

    recuperados = 0
    enviados_quarentena = 0
    for lote in abandonados:
        tentativas = lote.tentativas or 0
        if tentativas >= limite_tentativas:
            valores = {
                'status': STATUS_QUARENTENA,
                'erro_codigo': 'LIMITE_TENTATIVAS_RECUPERACAO',
                'erro_mensagem': 'Lote interrompido repetidamente e direcionado à quarentena',
                'atualizado_em': instante,
                'processado_em': instante,
            }
        else:
            valores = {
                'status': STATUS_PENDENTE,
                'erro_codigo': 'RECUPERADO_APOS_INTERRUPCAO',
                'erro_mensagem': 'Lote retornou à fila após processamento interrompido',
                'atualizado_em': instante,
                'processado_em': None,
            }

        resultado = db.execute(
            update(PentahoIntegrationBatch)
            .where(
                PentahoIntegrationBatch.id == lote.id,
                PentahoIntegrationBatch.status == STATUS_PROCESSANDO,
                condicao_abandono,
            )
            .values(**valores)
            .execution_options(synchronize_session=False)
        )
        if resultado.rowcount != 1:
            continue

        if valores['status'] == STATUS_QUARENTENA:
            enviados_quarentena += 1
        else:
            recuperados += 1
        logger.warning(
            'lote_pentaho_recuperado lote_id=%s correlation_id=%s novo_status=%s tentativas=%s',
            lote.lote_id,
            lote.correlation_id,
            valores['status'],
            tentativas,
        )

    db.commit()
    return {
        'recuperados': recuperados,
        'quarentena': enviados_quarentena,
        'avaliados': len(abandonados),
    }


def preparar_reprocessamento(db: Session, lote_id: str) -> PentahoIntegrationBatch:
    lote = obter_lote(db, lote_id)
    if lote.status != STATUS_QUARENTENA:
        raise HTTPException(status_code=409, detail='Somente lotes em QUARENTENA podem ser reprocessados')
    lote.status = STATUS_PENDENTE
    lote.erro_codigo = None
    lote.erro_mensagem = None
    lote.processado_em = None
    lote.atualizado_em = _agora()
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
