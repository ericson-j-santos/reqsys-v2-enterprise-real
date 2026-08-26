from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers

import app.api.documento_demanda as documento_api
from app.api.documento_demanda import (
    analisar_documento_demanda,
    obter_analise_documento,
    obter_prontidao_ocr_documento,
)
from app.models.documento_demanda import DocumentoDemandaAnalise
from app.ocr.documento_worker import OcrDocumentoResultado, OcrPaginaDocumento


def _arquivo(nome: str, content_type: str, conteudo: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(conteudo),
        filename=nome,
        headers=Headers({'content-type': content_type}),
    )


@pytest.fixture
def db_session():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    DocumentoDemandaAnalise.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


async def test_analisar_documento_texto_persiste_candidatos_sem_incorporacao_automatica(db_session):
    resposta = await analisar_documento_demanda(
        demanda_ref='DEM-001',
        arquivo=_arquivo('regras.txt', 'text/plain', b'O sistema deve validar o CPF informado.'),
        db=db_session,
        user={'sub': 'admin-teste'},
        x_correlation_id='corr-dem-001',
    )

    assert resposta['success'] is True
    assert resposta['data']['status'] == 'AGUARDANDO_REVISAO_HUMANA'
    assert resposta['data']['idempotente'] is False
    assert resposta['data']['incorporacao_automatica'] is False
    assert resposta['data']['candidatos'][0]['tipo'] == 'POSSIVEL_REQUISITO'

    registro = db_session.query(DocumentoDemandaAnalise).one()
    assert registro.demanda_ref == 'DEM-001'
    assert registro.correlation_id == 'corr-dem-001'


async def test_analisar_documento_repetido_e_idempotente(db_session):
    conteudo = b'Somente o gestor pode aprovar a solicitacao.'
    primeira = await analisar_documento_demanda(
        demanda_ref='DEM-002',
        arquivo=_arquivo('regra.txt', 'text/plain', conteudo),
        db=db_session,
        user={'sub': 'admin-teste'},
        x_correlation_id='corr-dem-002',
    )
    segunda = await analisar_documento_demanda(
        demanda_ref='DEM-002',
        arquivo=_arquivo('regra.txt', 'text/plain', conteudo),
        db=db_session,
        user={'sub': 'admin-teste'},
        x_correlation_id='corr-ignorado-no-replay',
    )

    assert primeira['data']['idempotente'] is False
    assert segunda['data']['idempotente'] is True
    assert segunda['data']['id'] == primeira['data']['id']
    assert segunda['meta']['correlation_id'] == 'corr-dem-002'
    assert db_session.query(DocumentoDemandaAnalise).count() == 1


async def test_analisar_documento_binario_fica_aguardando_ocr_quando_flag_desligada(db_session, monkeypatch):
    monkeypatch.delenv('DOCUMENTO_DEMANDA_OCR_ENABLED', raising=False)
    resposta = await analisar_documento_demanda(
        demanda_ref='DEM-003',
        arquivo=_arquivo('evidencia.pdf', 'application/pdf', b'%PDF-1.7 conteudo-binario'),
        db=db_session,
        user={'sub': 'admin-teste'},
        x_correlation_id='corr-dem-003',
    )

    assert resposta['data']['status'] == 'AGUARDANDO_OCR'
    assert resposta['data']['candidatos'] == []
    assert resposta['data']['incorporacao_automatica'] is False


async def test_analisar_pdf_com_ocr_habilitado_classifica_com_evidencia_de_pagina(db_session, monkeypatch):
    class MotorFake:
        def processar(self, entrada, *, content_type):
            assert entrada.name.endswith('.pdf')
            assert content_type == 'application/pdf'
            return OcrDocumentoResultado(
                paginas=(
                    OcrPaginaDocumento(1, 'O sistema deve validar o CPF informado.', 0.93),
                    OcrPaginaDocumento(2, 'Somente o gestor pode aprovar a solicitação.', 0.81),
                )
            )

    monkeypatch.setenv('DOCUMENTO_DEMANDA_OCR_ENABLED', 'true')
    monkeypatch.setattr(documento_api, '_novo_motor_ocr_documento', lambda: MotorFake())

    resposta = await analisar_documento_demanda(
        demanda_ref='DEM-OCR-001',
        arquivo=_arquivo('evidencia.pdf', 'application/pdf', b'%PDF-1.7 teste-ocr'),
        db=db_session,
        user={'sub': 'admin-teste'},
        x_correlation_id='corr-ocr-001',
    )

    assert resposta['data']['status'] == 'AGUARDANDO_REVISAO_HUMANA'
    assert resposta['data']['incorporacao_automatica'] is False
    assert [item['pagina'] for item in resposta['data']['candidatos']] == [1, 2]
    assert resposta['data']['candidatos'][0]['confianca'] == 0.7
    assert resposta['data']['candidatos'][1]['confianca'] == 0.7
    registro = db_session.query(DocumentoDemandaAnalise).one()
    assert 'validar o CPF' in registro.texto_extraido
    assert registro.erro == ''


async def test_falha_ocr_persiste_erro_sem_incorporar_e_reenvio_recupera_mesmo_registro(db_session, monkeypatch):
    class MotorFalha:
        def processar(self, entrada, *, content_type):
            raise RuntimeError('falha interna com dado que não deve vazar')

    class MotorRecuperado:
        def processar(self, entrada, *, content_type):
            return OcrDocumentoResultado(
                paginas=(OcrPaginaDocumento(1, 'O sistema deve registrar auditoria.', 0.88),)
            )

    monkeypatch.setenv('DOCUMENTO_DEMANDA_OCR_ENABLED', 'true')
    monkeypatch.setattr(documento_api, '_novo_motor_ocr_documento', lambda: MotorFalha())
    conteudo = b'%PDF-1.7 falha-controlada'

    with pytest.raises(HTTPException) as exc_info:
        await analisar_documento_demanda(
            demanda_ref='DEM-OCR-002',
            arquivo=_arquivo('falha.pdf', 'application/pdf', conteudo),
            db=db_session,
            user={'sub': 'admin-teste'},
            x_correlation_id='corr-ocr-002',
        )

    assert exc_info.value.status_code == 503
    assert 'dado que não deve vazar' not in str(exc_info.value.detail)
    registro = db_session.query(DocumentoDemandaAnalise).one()
    primeiro_id = registro.id
    assert registro.status == 'ERRO_OCR'
    assert 'dado que não deve vazar' not in registro.erro

    monkeypatch.setattr(documento_api, '_novo_motor_ocr_documento', lambda: MotorRecuperado())
    resposta = await analisar_documento_demanda(
        demanda_ref='DEM-OCR-002',
        arquivo=_arquivo('falha.pdf', 'application/pdf', conteudo),
        db=db_session,
        user={'sub': 'admin-teste'},
        x_correlation_id='corr-novo-ignorado',
    )

    assert resposta['data']['idempotente'] is True
    assert resposta['data']['id'] == primeiro_id
    assert resposta['data']['status'] == 'AGUARDANDO_REVISAO_HUMANA'
    assert db_session.query(DocumentoDemandaAnalise).count() == 1


async def test_analisar_documento_rejeita_tipo_nao_suportado(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await analisar_documento_demanda(
            demanda_ref='DEM-004',
            arquivo=_arquivo('programa.exe', 'application/octet-stream', b'MZ'),
            db=db_session,
            user={'sub': 'admin-teste'},
            x_correlation_id='corr-dem-004',
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == 'tipo de arquivo não suportado'
    assert db_session.query(DocumentoDemandaAnalise).count() == 0


def test_prontidao_ocr_documento_expoe_flag_e_dependencias_sem_texto(monkeypatch):
    monkeypatch.delenv('DOCUMENTO_DEMANDA_OCR_ENABLED', raising=False)
    monkeypatch.setattr(
        documento_api,
        'ocr_documento_readiness',
        lambda: {'tesseract': True, 'pdftoppm': True, 'pdfinfo': True, 'ready_images': True, 'ready_pdf': True},
    )
    resposta = obter_prontidao_ocr_documento(user={'sub': 'admin-teste'})
    assert resposta['data']['enabled'] is False
    assert resposta['data']['ready_pdf'] is True
    assert 'texto' not in resposta['data']


def test_obter_analise_documento_existente_e_preserva_revisao_humana(db_session):
    registro = DocumentoDemandaAnalise(
        demanda_ref='DEM-005',
        nome_arquivo='regras.txt',
        content_type='text/plain',
        sha256='a' * 64,
        correlation_id='corr-dem-005',
        status='AGUARDANDO_REVISAO_HUMANA',
        texto_extraido='O sistema deve registrar auditoria.',
        candidatos_json='[{"tipo":"POSSIVEL_REQUISITO","texto":"O sistema deve registrar auditoria.","confianca":0.7,"requer_validacao_humana":true}]',
    )
    db_session.add(registro)
    db_session.commit()
    db_session.refresh(registro)

    resposta = obter_analise_documento(registro.id, db=db_session, user={'sub': 'admin-teste'})

    assert resposta['data']['id'] == registro.id
    assert resposta['data']['incorporacao_automatica'] is False
    assert resposta['data']['candidatos'][0]['requer_validacao_humana'] is True
    assert resposta['meta']['correlation_id'] == 'corr-dem-005'


def test_obter_analise_documento_inexistente_retorna_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        obter_analise_documento(999, db=db_session, user={'sub': 'admin-teste'})

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == 'Análise documental não encontrada'
