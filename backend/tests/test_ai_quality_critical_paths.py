"""Caminhos críticos — serviço ai_quality."""

import os

import pytest

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_ai_quality.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from datetime import datetime, timedelta, timezone

from app.db import Base, SessionLocal, engine
from app.models.auditoria import AuditoriaEvento
from app.models.requisito import Requisito
from app.services.ai_quality import (
    _clip,
    _safe_pct,
    calcular_resumo_qualidade_ia,
    exportar_tendencia_csv,
    exportar_tendencia_pdf,
    listar_tendencia,
    registrar_snapshot_qualidade_ia,
)


@pytest.fixture(scope='module', autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_safe_pct_e_clip_limites():
    assert _safe_pct(0, 0) == 0.0
    assert _safe_pct(2, 4) == 50.0
    assert _clip(150) == 100.0
    assert _clip(-5) == 0.0


def test_calcular_resumo_qualidade_ia_com_requisitos_e_incidentes():
    db = SessionLocal()
    codigos = ['REQ-AI-001', 'REQ-AI-002']
    try:
        db.query(AuditoriaEvento).filter(AuditoriaEvento.correlation_id == 'corr-ai-quality').delete()
        db.query(Requisito).filter(Requisito.codigo.in_(codigos)).delete()
        db.commit()

        db.add(
            Requisito(
                codigo='REQ-AI-001',
                titulo='Requisito com descricao longa para cobertura',
                descricao='Descricao detalhada com mais de quarenta caracteres para qualidade IA.',
                status='aprovado',
                urgencia='alta',
                area='QA',
                sistema='ReqSys',
                solicitante='qa@reqsys.local',
            )
        )
        db.add(
            Requisito(
                codigo='REQ-AI-002',
                titulo='Pendente',
                descricao='Descricao pendente com tamanho minimo aceitavel para validacao.',
                status='pendente',
                urgencia='media',
                area='QA',
                sistema='ReqSys',
                solicitante='qa@reqsys.local',
            )
        )
        db.add(
            AuditoriaEvento(
                acao='erro_critico_pipeline',
                entidade='requisito',
                entidade_id='1',
                correlation_id='corr-ai-quality',
                usuario='tester',
                criado_em=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        db.commit()

        resumo = calcular_resumo_qualidade_ia(db)

        assert resumo['status'] in {'excelente', 'estavel', 'atencao', 'critico'}
        assert resumo['metricas']['acuracia'] >= 0
        assert isinstance(resumo['recomendacoes'], list)
        assert len(resumo['recomendacoes']) >= 1
    finally:
        db.query(AuditoriaEvento).filter(AuditoriaEvento.correlation_id == 'corr-ai-quality').delete()
        db.query(Requisito).filter(Requisito.codigo.in_(codigos)).delete()
        db.commit()
        db.close()


def test_calcular_resumo_qualidade_ia_recomendacao_manutencao_quando_saudavel():
    db = SessionLocal()
    codigos = [f'REQ-AI-OK-{idx}' for idx in range(3)]
    try:
        db.query(Requisito).filter(Requisito.codigo.in_(codigos)).delete()
        db.commit()

        for idx in range(3):
            db.add(
                Requisito(
                    codigo=f'REQ-AI-OK-{idx}',
                    titulo=f'Requisito saudavel {idx}',
                    descricao='Descricao longa e consistente para manter cobertura de dados em qualidade IA.',
                    status='aprovado',
                    urgencia='alta',
                    area='QA',
                    sistema='ReqSys',
                    solicitante='qa@reqsys.local',
                )
            )
        db.commit()

        resumo = calcular_resumo_qualidade_ia(db)

        assert resumo['status'] in {'excelente', 'estavel', 'atencao'}
        assert resumo['recomendacoes']
    finally:
        db.query(Requisito).filter(Requisito.codigo.in_(codigos)).delete()
        db.commit()
        db.close()


def test_registrar_snapshot_e_exportacoes():
    db = SessionLocal()
    codigo = 'REQ-AI-SNAPSHOT-001'
    try:
        db.query(Requisito).filter(Requisito.codigo == codigo).delete()
        db.commit()
        db.add(
            Requisito(
                codigo=codigo,
                titulo='Snapshot qualidade IA',
                descricao='Descricao longa para registrar snapshot de qualidade IA no teste.',
                status='aprovado',
                urgencia='alta',
                area='QA',
                sistema='ReqSys',
                solicitante='qa@reqsys.local',
            )
        )
        db.commit()

        registrado = registrar_snapshot_qualidade_ia(db)
        assert registrado['id'] > 0

        tendencia = listar_tendencia(db, limit=5, dias=30)
        assert isinstance(tendencia, list)

        csv_data = exportar_tendencia_csv(tendencia)
        assert 'score_geral' in csv_data

        pdf_bytes = exportar_tendencia_pdf(tendencia)
        assert pdf_bytes.startswith(b'%PDF')

        pdf_vazio = exportar_tendencia_pdf([])
        assert b'Sem snapshots disponiveis' in pdf_vazio
    finally:
        db.query(Requisito).filter(Requisito.codigo == codigo).delete()
        db.commit()
        db.close()
