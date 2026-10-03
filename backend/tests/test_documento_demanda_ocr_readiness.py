import app.ocr.documento_worker as worker


def test_readiness_indica_dependencias_ausentes(monkeypatch):
    monkeypatch.setattr(worker.shutil, 'which', lambda nome: None)
    status = worker.ocr_documento_readiness()
    assert status == {
        'tesseract': False,
        'pdftoppm': False,
        'pdfinfo': False,
        'ready_images': False,
        'ready_pdf': False,
    }


def test_readiness_pdf_exige_todas_as_dependencias(monkeypatch):
    disponiveis = {'tesseract': '/usr/bin/tesseract', 'pdftoppm': '/usr/bin/pdftoppm'}
    monkeypatch.setattr(worker.shutil, 'which', lambda nome: disponiveis.get(nome))
    status = worker.ocr_documento_readiness()
    assert status['ready_images'] is True
    assert status['ready_pdf'] is False
