from app.services.documento_demanda import classificar_candidatos_por_paginas


def test_candidato_ocr_continua_exigindo_validacao_humana():
    candidatos = classificar_candidatos_por_paginas(
        [(1, 'O sistema deve registrar o histórico da demanda.', 0.99)]
    )
    assert len(candidatos) == 1
    assert candidatos[0].requer_validacao_humana is True
