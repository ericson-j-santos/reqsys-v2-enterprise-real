import app.api.documento_demanda as documento_api


def test_flag_ocr_so_habilita_em_dev_ou_testes(monkeypatch):
    monkeypatch.setenv('DOCUMENTO_DEMANDA_OCR_ENABLED', 'true')
    original = documento_api.settings.app_environment
    try:
        documento_api.settings.app_environment = 'production'
        assert documento_api._ocr_documento_habilitado() is False
        documento_api.settings.app_environment = 'staging'
        assert documento_api._ocr_documento_habilitado() is False
        documento_api.settings.app_environment = 'development'
        assert documento_api._ocr_documento_habilitado() is True
        documento_api.settings.app_environment = 'test'
        assert documento_api._ocr_documento_habilitado() is True
    finally:
        documento_api.settings.app_environment = original
