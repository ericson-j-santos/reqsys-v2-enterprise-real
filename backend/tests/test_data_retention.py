from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.auditoria import AuditoriaEvento
from app.services.data_retention import (
    DEFAULT_AUDITORIA_RETENTION_DAYS,
    purgar_auditoria_eventos,
)


@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _inserir_evento(db, dias_atras: int, acao: str = 'REQUISITO_CRIADO'):
    evento = AuditoriaEvento(
        correlation_id=f'corr-{dias_atras}',
        usuario='teste@reqsys.local',
        acao=acao,
        entidade='requisito',
        entidade_id='1',
        payload_minimo='{}',
    )
    db.add(evento)
    db.commit()
    # criado_em usa server_default=func.now(); sobrescreve direto no banco para simular idade real
    cutoff = datetime.now(timezone.utc) - timedelta(days=dias_atras)
    db.query(AuditoriaEvento).filter(AuditoriaEvento.id == evento.id).update({'criado_em': cutoff})
    db.commit()
    return evento.id


def test_purge_remove_apenas_eventos_mais_antigos_que_a_retencao(db_session):
    antigo_id = _inserir_evento(db_session, dias_atras=200)
    recente_id = _inserir_evento(db_session, dias_atras=5)

    resultado = purgar_auditoria_eventos(db_session, retention_days=180)

    assert resultado['registros_removidos'] == 1
    ids_restantes = {e.id for e in db_session.query(AuditoriaEvento).all()}
    # o proprio evento AUDITORIA_PURGE_EXECUTADO gerado pela purga tambem fica na tabela
    assert antigo_id not in ids_restantes
    assert recente_id in ids_restantes


def test_purge_gera_evento_de_auditoria_quando_remove_algo(db_session):
    _inserir_evento(db_session, dias_atras=400)

    purgar_auditoria_eventos(db_session, retention_days=180, correlation_id='corr-teste-purge')

    evento_purge = (
        db_session.query(AuditoriaEvento)
        .filter(AuditoriaEvento.acao == 'AUDITORIA_PURGE_EXECUTADO')
        .one_or_none()
    )
    assert evento_purge is not None
    assert evento_purge.correlation_id == 'corr-teste-purge'


def test_purge_nao_gera_evento_quando_nao_ha_nada_para_remover(db_session):
    _inserir_evento(db_session, dias_atras=5)

    resultado = purgar_auditoria_eventos(db_session, retention_days=180)

    assert resultado['registros_removidos'] == 0
    evento_purge = (
        db_session.query(AuditoriaEvento)
        .filter(AuditoriaEvento.acao == 'AUDITORIA_PURGE_EXECUTADO')
        .one_or_none()
    )
    assert evento_purge is None


def test_purge_usa_retencao_default_quando_nao_configurada(monkeypatch, db_session):
    monkeypatch.delenv('AUDITORIA_RETENTION_DAYS', raising=False)
    _inserir_evento(db_session, dias_atras=DEFAULT_AUDITORIA_RETENTION_DAYS + 10)

    resultado = purgar_auditoria_eventos(db_session)

    assert resultado['retention_days'] == DEFAULT_AUDITORIA_RETENTION_DAYS
    assert resultado['registros_removidos'] == 1


def test_purge_respeita_override_via_env(monkeypatch, db_session):
    monkeypatch.setenv('AUDITORIA_RETENTION_DAYS', '30')
    _inserir_evento(db_session, dias_atras=60)

    resultado = purgar_auditoria_eventos(db_session)

    assert resultado['retention_days'] == 30
    assert resultado['registros_removidos'] == 1
