import app.api.documento_demanda as documento_api


class MotorCaptura:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_factory_ocr_aplica_limites_padrao(monkeypatch):
    monkeypatch.delenv('DOCUMENTO_DEMANDA_OCR_LANG', raising=False)
    monkeypatch.delenv('DOCUMENTO_DEMANDA_OCR_DPI', raising=False)
    monkeypatch.delenv('DOCUMENTO_DEMANDA_OCR_TIMEOUT_SECONDS', raising=False)
    monkeypatch.delenv('DOCUMENTO_DEMANDA_OCR_MAX_PAGES', raising=False)
    monkeypatch.setattr(documento_api, 'TesseractDocumento', MotorCaptura)
    motor = documento_api._novo_motor_ocr_documento()
    assert motor.kwargs == {
        'idioma': 'por',
        'dpi_pdf': 200,
        'timeout_segundos': 60.0,
        'max_paginas': 25,
    }
