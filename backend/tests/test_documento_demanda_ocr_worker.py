from pathlib import Path

import pytest

from app.ocr.documento_worker import (
    EVENTO_OCR_DOCUMENTO_DEMANDA_SOLICITADO,
    DocumentoDemandaOcrWorker,
    OcrDocumentoResultado,
    OcrPaginaDocumento,
    RepositorioOcrDocumentoMemoria,
    _ler_tsv,
)
from app.services.runtime_core import RuntimeEventEnvelope


class MotorFake:
    def processar(self, entrada: Path, *, content_type: str) -> OcrDocumentoResultado:
        return OcrDocumentoResultado(
            paginas=(OcrPaginaDocumento(1, 'O sistema deve validar o documento.', 0.91),)
        )


def _evento(**payload):
    return RuntimeEventEnvelope(
        event_type=EVENTO_OCR_DOCUMENTO_DEMANDA_SOLICITADO,
        source='teste',
        aggregate_type='documento_demanda_ocr',
        aggregate_id='10',
        correlation_id='corr-worker',
        payload=payload,
    )


def test_worker_processa_referencia_relativa_sem_publicar_conteudo(tmp_path):
    entrada = tmp_path / 'abc.pdf'
    entrada.write_bytes(b'%PDF-1.7 teste')
    repositorio = RepositorioOcrDocumentoMemoria()
    worker = DocumentoDemandaOcrWorker(MotorFake(), repositorio, input_root=tmp_path)
    evento = _evento(document_ref='abc.pdf', content_type='application/pdf')

    worker(evento)

    resultado = repositorio.obter('10')
    assert resultado is not None
    assert resultado.paginas[0].pagina == 1
    assert 'deve validar' in resultado.texto
    assert 'texto' not in evento.payload


def test_worker_rejeita_path_absoluto(tmp_path):
    worker = DocumentoDemandaOcrWorker(MotorFake(), RepositorioOcrDocumentoMemoria(), input_root=tmp_path)
    with pytest.raises(ValueError, match='relativo'):
        worker(_evento(document_ref=str((tmp_path / 'arquivo.pdf').resolve()), content_type='application/pdf'))


def test_worker_rejeita_path_traversal(tmp_path):
    worker = DocumentoDemandaOcrWorker(MotorFake(), RepositorioOcrDocumentoMemoria(), input_root=tmp_path)
    with pytest.raises(ValueError, match='escapou'):
        worker(_evento(document_ref='../fora.pdf', content_type='application/pdf'))


def test_worker_rejeita_evento_incorreto(tmp_path):
    worker = DocumentoDemandaOcrWorker(MotorFake(), RepositorioOcrDocumentoMemoria(), input_root=tmp_path)
    evento = RuntimeEventEnvelope(
        event_type='OUTRO_EVENTO',
        source='teste',
        aggregate_type='documento_demanda_ocr',
        aggregate_id='10',
    )
    with pytest.raises(ValueError, match='evento não suportado'):
        worker(evento)


def test_ler_tsv_reconstroi_linhas_e_calcula_confianca():
    tsv = (
        'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
        '5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90\tO\n'
        '5\t1\t1\t1\t1\t2\t0\t0\t10\t10\t80\tsistema\n'
        '5\t1\t1\t1\t2\t1\t0\t0\t10\t10\t70\tdeve\n'
    )
    texto, confianca = _ler_tsv(tsv)
    assert texto == 'O sistema\ndeve'
    assert confianca == 0.8
