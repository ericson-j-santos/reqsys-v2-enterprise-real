from pathlib import Path

from app.ocr.documento_worker import _numero_pagina


def test_numero_pagina_ordena_sufixo_numerico():
    paginas = [Path('pagina-10.png'), Path('pagina-2.png'), Path('pagina-1.png')]
    ordenadas = sorted(paginas, key=_numero_pagina)
    assert [item.name for item in ordenadas] == ['pagina-1.png', 'pagina-2.png', 'pagina-10.png']
