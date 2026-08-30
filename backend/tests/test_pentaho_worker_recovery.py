from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.models.pentaho_integration_batch import PentahoIntegrationBatch
from app.schemas.pentaho_integration import PentahoLoteEntrada
from app.services.pentaho_integration import (
    STATUS_CONCLUIDO,
    STATUS_PENDENTE,
    STATUS_PROCESSANDO,
    STATUS_QUARENTENA,
    criar_ou_obter_lote,
    processar_proximo_lote,
    recuperar_lotes_abandonados,
    reivindicar_lote,
)


def _entrada() -> PentahoLoteEntrada:
    return PentahoLoteEntrada(
        origem='PENTAHO',
        processo='TESTE_WORKER_RECUPERACAO',
        versaoEntrada=1,
        dataReferencia='2026-08-29',
        lote=f'lote-{uuid4()}',
        registros=[{'produto': 10001, 'canal': 'WEB'}],
    )


def _criar_lote(db_session):
    lote, duplicado = criar_ou_obter_lote(
        db_session,
        _entrada(),
        idempotency_key=f'idem-{uuid4()}',
        correlation_id=f'corr-{uuid4()}',
    )
    assert duplicado is False
    return lote


def test_reivindicacao_atomica_impede_duplo_consumo(db_session):
    lote = _criar_lote(db_session)

    primeira = reivindicar_lote(db_session, lote.lote_id)
    segunda = reivindicar_lote(db_session, lote.lote_id)

    assert primeira is not None
    assert primeira.status == STATUS_PROCESSANDO
    assert segunda is None

    persistido = db_session.query(PentahoIntegrationBatch).filter_by(lote_id=lote.lote_id).one()
    assert persistido.tentativas == 1


def test_recupera_lote_abandonado_e_worker_conclui_sem_duplicar(db_session):
    lote = _criar_lote(db_session)
    agora = datetime.now(timezone.utc)
    lote.status = STATUS_PROCESSANDO
    lote.tentativas = 1
    lote.atualizado_em = agora - timedelta(minutes=10)
    db_session.add(lote)
    db_session.commit()

    recuperacao = recuperar_lotes_abandonados(
        db_session,
        agora=agora,
        timeout_segundos=300,
        max_tentativas=5,
    )

    assert recuperacao == {'recuperados': 1, 'quarentena': 0, 'avaliados': 1}
    recuperado = db_session.query(PentahoIntegrationBatch).filter_by(lote_id=lote.lote_id).one()
    assert recuperado.status == STATUS_PENDENTE
    assert recuperado.erro_codigo == 'RECUPERADO_APOS_INTERRUPCAO'

    processado_id = processar_proximo_lote(db_session)
    assert processado_id == lote.lote_id

    concluido = db_session.query(PentahoIntegrationBatch).filter_by(lote_id=lote.lote_id).one()
    assert concluido.status == STATUS_CONCLUIDO
    assert concluido.tentativas == 2
    assert concluido.registros_aceitos == 1
    assert concluido.erro_codigo is None


def test_interrupcoes_repetidas_vão_para_quarentena(db_session):
    lote = _criar_lote(db_session)
    agora = datetime.now(timezone.utc)
    lote.status = STATUS_PROCESSANDO
    lote.tentativas = 5
    lote.atualizado_em = agora - timedelta(minutes=10)
    db_session.add(lote)
    db_session.commit()

    recuperacao = recuperar_lotes_abandonados(
        db_session,
        agora=agora,
        timeout_segundos=300,
        max_tentativas=5,
    )

    assert recuperacao == {'recuperados': 0, 'quarentena': 1, 'avaliados': 1}
    persistido = db_session.query(PentahoIntegrationBatch).filter_by(lote_id=lote.lote_id).one()
    assert persistido.status == STATUS_QUARENTENA
    assert persistido.erro_codigo == 'LIMITE_TENTATIVAS_RECUPERACAO'


def test_recuperacao_ignora_lote_alterado_em_disputa_concorrente(db_session, monkeypatch):
    lote = _criar_lote(db_session)
    agora = datetime.now(timezone.utc)
    lote.status = STATUS_PROCESSANDO
    lote.tentativas = 1
    lote.atualizado_em = agora - timedelta(minutes=10)
    db_session.add(lote)
    db_session.commit()

    executar_original = db_session.execute

    def executar_simulando_disputa(statement, *args, **kwargs):
        if getattr(statement, 'is_update', False):
            return SimpleNamespace(rowcount=0)
        return executar_original(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, 'execute', executar_simulando_disputa)

    recuperacao = recuperar_lotes_abandonados(
        db_session,
        agora=agora,
        timeout_segundos=300,
        max_tentativas=5,
    )

    assert recuperacao == {'recuperados': 0, 'quarentena': 0, 'avaliados': 1}
    persistido = db_session.query(PentahoIntegrationBatch).filter_by(lote_id=lote.lote_id).one()
    assert persistido.status == STATUS_PROCESSANDO
    assert persistido.tentativas == 1
