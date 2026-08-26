from pathlib import Path

import pytest

import app.ocr.documento_worker as worker
from app.ocr.documento_worker import FalhaOcrDocumento, TesseractDocumento


def _motor_sem_init() -> TesseractDocumento:
    motor = object.__new__(TesseractDocumento)
    motor.idioma = 'por'
    motor.dpi_pdf = 200
    motor.timeout_segundos = 1.0
    motor.max_paginas = 2
    motor.tesseract = '/usr/bin/tesseract'
    motor.pdftoppm = '/usr/bin/pdftoppm'
    motor.pdfinfo = '/usr/bin/pdfinfo'
    return motor


def test_validar_paginas_pdf_rejeita_documento_acima_limite(tmp_path, monkeypatch):
    entrada = tmp_path / 'doc.pdf'
    entrada.write_bytes(b'%PDF')
    motor = _motor_sem_init()
    monkeypatch.setattr(
        worker,
        '_executar',
        lambda cmd, timeout: type('Proc', (), {'stdout': 'Pages:          3\n', 'returncode': 0})(),
    )
    with pytest.raises(FalhaOcrDocumento, match='limite de 2 páginas'):
        motor._validar_paginas_pdf(entrada)


def test_processar_rejeita_tipo_fora_do_ocr(tmp_path):
    entrada = tmp_path / 'doc.txt'
    entrada.write_text('texto', encoding='utf-8')
    motor = _motor_sem_init()
    with pytest.raises(ValueError, match='tipo de arquivo'):
        motor.processar(Path(entrada), content_type='text/plain')
